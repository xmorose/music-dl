#!/usr/bin/env python
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mutagen
from mutagen.id3 import ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK, TXXX
from mutagen.mp4 import MP4, MP4FreeForm

TITLE_JUNK = r"\s*[\(\[]\s*(?:Official|Music|Lyric|Audio|HD|HQ|4K|Video|Visualizer|Visualiser).*?[\)\]]"
# what yt-dlp hands back per downloaded file, for retag()
INFO_FIELDS = "filepath,fulltitle,title,track,artists,creators,artist,uploader,album,release_year,track_number"


def output_dir(arg):
    if arg:
        return Path(arg)
    env = os.environ.get("MUSIC_DL_DIR")
    return Path(env) if env else Path("Music")


def detect(url):
    u = url.lower()
    if "open.spotify.com" in u or u.startswith("spotify:"):
        return "spotify"
    if "tidal.com" in u:
        return "tidal"
    return "ytdlp"


def spotify_cmd(url, out):
    return [
        "spotdl", "download", url,
        "--output", str(out / "{artist}/{album}/{track-number} - {title}.{output-ext}"),
        "--format", "mp3",
        "--bitrate", "320k",
    ]


def tidal_cmd(url, out):
    return ["rip", "url", url, "--directory", str(out)]


def ytdlp_cmd(url, out, info_file=None, audio_format="best"):
    cmd = [
        "yt-dlp", "-x",
        "--audio-format", audio_format,  # best = the source audio as is, no re-encode
        "--audio-quality", "0",
        "--embed-metadata",
        "--embed-thumbnail",
        "--replace-in-metadata", "title", TITLE_JUNK, "",
        "--parse-metadata", "title:^(?P<artist>.+?) - (?P<title>.+)$",
        "--parse-metadata", "%(album,title)s:%(meta_album)s",
        "-o", str(out / "%(artists.0,creators.0,artist,uploader)s/%(album,playlist|Singles)s/%(title)s.%(ext)s"),
    ]
    if info_file:
        cmd += ["--print-to-file", "after_move:%(.{" + INFO_FIELDS + "})j", str(info_file)]
    return cmd + [url]


def dedupe(names):
    seen, out = set(), []
    for n in (n.strip() for n in names):
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def pick_artists(info):
    """YouTube's own artist list if it has one, else the single artist from the title or uploader."""
    for key in ("artists", "creators"):
        names = dedupe(info.get(key) or [])
        if names:
            return names
    name = info.get("artist") or info.get("uploader") or ""
    return [name.removesuffix(" - Topic")] if name else []


def pick_title(info, artists):
    if info.get("track"):
        return info["track"]
    # "ABOUT IT! - Foolish Animals - Swisho": drop the parts that are known artists
    parts = [p.strip() for p in re.sub(TITLE_JUNK, "", info.get("fulltitle") or "").split(" - ")]
    rest = [p for p in parts if p not in artists]
    if len(parts) > 1 and len(rest) == 1:
        return rest[0]
    return info.get("title")


def write_id3(path, tags):
    t = ID3(path)
    for frame, key in ((TPE1, "artist"), (TPE2, "albumartist"), (TIT2, "title"), (TALB, "album"), (TDRC, "date")):
        if tags[key]:
            t.setall(frame.__name__, [frame(encoding=3, text=[tags[key]])])
    t.delall("TXXX:ARTISTS")
    t.add(TXXX(encoding=3, desc="ARTISTS", text=tags["artists"]))
    # the ID3v1 tag ffmpeg adds puts the "?" of the truncated URL comment into the track byte (track 63)
    t.delall("COMM:ID3v1 Comment")
    if tags["track"]:
        t.setall("TRCK", [TRCK(encoding=3, text=[tags["track"]])])
    else:
        t.delall("TRCK")
    if "TCON" in t and [str(x) for x in t["TCON"].text] == ["Music"]:
        t.delall("TCON")
    t.save(path, v1=0, v2_version=4)  # v2.3 would join ARTISTS with "/"


def write_mp4(path, tags):
    m = MP4(path)
    for atom, key in (("\xa9ART", "artist"), ("aART", "albumartist"), ("\xa9nam", "title"), ("\xa9alb", "album"), ("\xa9day", "date")):
        if tags[key]:
            m[atom] = [tags[key]]
    m["----:com.apple.iTunes:ARTISTS"] = [MP4FreeForm(a.encode("utf-8")) for a in tags["artists"]]
    if tags["track"]:
        m["trkn"] = [(int(tags["track"]), 0)]
    if m.get("\xa9gen") == ["Music"]:
        del m["\xa9gen"]
    m.save()


def write_vorbis(path, tags):
    m = mutagen.File(path)
    for field, key in (("ARTIST", "artist"), ("ALBUMARTIST", "albumartist"), ("TITLE", "title"), ("ALBUM", "album"), ("DATE", "date"), ("TRACKNUMBER", "track")):
        if tags[key]:
            m[field] = [tags[key]]
    m["ARTISTS"] = tags["artists"]
    if m.get("GENRE") == ["Music"]:
        del m["GENRE"]
    m.save()


WRITERS = {".mp3": write_id3, ".m4a": write_mp4, ".opus": write_vorbis, ".ogg": write_vorbis, ".flac": write_vorbis}


def retag(info):
    """Give each artist its own value (ARTISTS) and always set an album artist, so Navidrome credits them separately."""
    path = info["filepath"]
    writer = WRITERS.get(Path(path).suffix.lower())
    artists = pick_artists(info)
    if not writer or not artists:
        return
    title = pick_title(info, artists)
    writer(path, {
        "artist": ", ".join(artists),
        "albumartist": artists[0],
        "artists": artists,
        "title": title,
        "album": (info.get("album") or title) if title else None,
        "date": str(info["release_year"]) if info.get("release_year") else None,
        "track": str(info["track_number"]) if info.get("track_number") else None,
    })
    print(f"tagged: {', '.join(artists)} - {title}")


BACKENDS = {
    "spotify": ("spotdl", spotify_cmd),
    "tidal": ("rip", tidal_cmd),
    "ytdlp": ("yt-dlp", ytdlp_cmd),
}


def clipboard():
    cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard"
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, timeout=3,
        )
        return r.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(prog="music-dl")
    parser.add_argument("url", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("-f", "--format", default="best",
                        help="audio format for yt-dlp downloads: best keeps the source audio without re-encoding "
                             "(default), or convert to mp3, flac, m4a, opus")
    args = parser.parse_args()

    url = args.url
    if not url:
        clip = clipboard()
        if clip.startswith("http"):
            url = clip
            print(f"clipboard: {url}")
        else:
            url = input("URL: ").strip()
    if not url:
        sys.exit("no url given")

    out = output_dir(args.output)
    src = detect(url)
    binary, build = BACKENDS[src]
    if not shutil.which(binary):
        sys.exit(f"{binary} not found, install it to download from {src}")
    if src != "ytdlp":
        sys.exit(subprocess.run(build(url, out)).returncode)

    with tempfile.TemporaryDirectory() as tmp:
        info_file = Path(tmp) / "info.jsonl"
        code = subprocess.run(ytdlp_cmd(url, out, info_file, args.format)).returncode
        if info_file.exists():
            for line in info_file.read_text(encoding="utf-8").splitlines():
                info = json.loads(line)
                try:
                    retag(info)
                except Exception as e:
                    print(f"retag failed for {info.get('filepath')}: {e}", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
