# MUSIC-CLI

A minimal and elegant command-line tool to search, play, and download music from YouTube. Powered by `yt-dlp`, `mpv`, and a beautiful UI from the `rich` library.

## Features

* 🎵 Search and stream YouTube audio in real-time
* 💾 Download any track directly as high-quality MP3
* 🧠 Maintains a playback history (stored in `history.json`)
* ⚡ Fast, clean, and distraction-free terminal experience

## Requirements

* Python 3.7+
* [`mpv`](https://mpv.io/) media player (must be installed separately)
* Python dependencies listed in `dependencies.txt`

## Install

```bash
git clone https://github.com/lamsal27/music-cli
cd music-cli
pip install -r dependencies.txt
```

## Usage

```bash
python music_cli.py play "song name"
python music_cli.py download "song name"
python music_cli.py help
```

## History

Each played track is recorded in `history.json` with the song title, date of play, and source URL.

## Dependencies

See `dependencies.txt` for required Python packages. Install with:

```bash
pip install -r dependencies.txt
```

## License

MIT

---

Built with ❤️ by [@lamsal27](https://github.com/lamsal27)
