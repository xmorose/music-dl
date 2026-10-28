# music-dl

A small command line tool that downloads music from a URL and sorts it into an
Artist/Album/Track folder structure, ready for Navidrome or any library that
reads folders and tags.

It picks the backend from the URL:

- Spotify -> spotdl
- Tidal -> streamrip
- everything else (YouTube, SoundCloud, Bandcamp, and so on) -> yt-dlp

## Install

```
pip install music-dl
```

That gives you the yt-dlp backend. Add the others as you need them:

```
pip install music-dl[spotify]   # adds spotdl
pip install music-dl[tidal]     # adds streamrip
pip install music-dl[all]
```

You also need [ffmpeg](https://ffmpeg.org/) on your PATH for audio extraction.

## Usage

```
music-dl https://www.youtube.com/watch?v=...
music-dl https://open.spotify.com/track/...
```

Run it without a URL and it reads one from the clipboard (Windows), falling back
to a prompt:

```
music-dl
```

## Where files go

Downloads land in `./Music` by default. Override it per run or globally:

```
music-dl -o /path/to/library <url>
export MUSIC_DL_DIR=/path/to/library   # used when -o is omitted
```

I keep `MUSIC_DL_DIR` pointed at my Navidrome library so new tracks show up on
the next scan.

## Audio format (yt-dlp)

By default the audio is saved exactly as the site serves it, usually Opus from
YouTube, without re-encoding. YouTube has no lossless audio, so this is the best
quality you can get, and converting it would only lose more. Pass `-f` to convert
anyway, for players that need a specific format:

```
music-dl -f mp3 <url>    # also flac, m4a, opus
```

## Tags (yt-dlp)

After a yt-dlp download the file is retagged (mp3, opus, ogg, flac, m4a) so
Navidrome credits every artist separately:

- `ARTISTS` holds one value per artist, taken from YouTube's own artist list
  (YouTube Music uploads and videos with credited artists). Without that list
  the artist from the "Artist - Title" video title or the uploader is used as is,
  never split by guessing.
- The album artist is always set to the first artist, and the folder is named
  after it.
- Bogus values are dropped: track number 63 from ffmpeg's ID3v1 tag and the
  genre "Music" (YouTube's video category).

## License

MIT
