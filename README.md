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

## License

MIT
