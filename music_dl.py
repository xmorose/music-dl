#!/usr/bin/env python
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def ytdlp_cmd(url, out):
    return [
        "yt-dlp", "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "--embed-thumbnail",
        "--replace-in-metadata", "title",
        r"\s*[\(\[]\s*(?:Official|Music|Lyric|Audio|HD|HQ|4K|Video|Visualizer|Visualiser).*?[\)\]]", "",
        "--parse-metadata", "title:^(?P<artist>[^-]+) - (?P<title>.+)$",
        "-o", str(out / "%(artist,uploader)s/%(album,playlist|Singles)s/%(title)s.%(ext)s"),
        url,
    ]


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
    sys.exit(subprocess.run(build(url, out)).returncode)


if __name__ == "__main__":
    main()
