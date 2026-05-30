# Music-CLI

Modern minimal terminal music player. Searches YouTube, streams via mpv or any preferred audio player.

## Dependencies


For windows:
`pip install yt-dlp rich` 

For Linux & MAC:
`pip install yt-dlp rich --break-system-packages` 

Install [mpv](https://mpv.io/installation/) separately.
Install [yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Installation).

## Usage

**Interactive mode**

```
python music.py
```

Type a song title to search. Results appear as a numbered table — enter a number to play, `d3` to download #3. Navigate with single-letter shortcuts: `l` library, `h` history, `,` settings, `0` exit.

**Direct play**

```
python music.py "Teri Ore"
```

Searches, shows results, plays the first match. No prompts.


## Usage Examples 

Play directly:

```
python music.py "Bheegi Si Bhaagi Si"
python music.py "Linkin park - Numb"
python music.py "Best of Mozart"
```

#  Or use (After adding global alias, To add the global alias read below)
```
music "Bheegi Si Bhaagi Si"  
music "Linkin Park - Numb"
music "Best of Mozart"
```

Open interactive mode:

```
music
```


## Global Command Alias

Use Music-CLI directly from terminal after setting it up properly from the given steps:

```
music "Bheegi Si Bhaagi Si"
```
This command directly plays the music directly. This is the simplest way to listen music. 

### Linux / macOS

Add to `~/.bashrc` or `~/.zshrc`:

```
alias music='python ~/music-cli/music.py'
```
Here, replace `~/music-cli/music.py` with the appropriate path.

Reload shell:

```
source ~/.bashrc
```

---

### Windows (PowerShell)

Open PowerShell profile:

```
notepad $PROFILE
```

Add:

```
function music {
    python "C:\path\music.py" $args
}
```

Here, replace `C:\path\music.py` with the appropriate path.

Restart PowerShell.


## How it works

- Searches your local history and YouTube simultaneously. Local matches appear first (marked `⊘`), online results after (`◈`).
- Streams by default. Set `auto_download: true` in settings to cache on play.
- Downloaded songs go to `~/Music` (Linux/macOS/Windows). Configurable.
- Play history and downloads tracked in a local SQLite database (`music.db`).

## Settings

Accessible from the interactive menu (`,`). Stored in `config.json` next to `music.py`.

| Key             | Default      | Description                        |
|-----------------|--------------|------------------------------------|
| download_dir    | ~/Music      | Where downloads are saved          |
| audio_format    | mp3          | mp3 / m4a / wav                    |
| audio_quality   | bestaudio    | bestaudio / 320 / 192 / worst      |
| search_limit    | 5          | Max YouTube results per search     |
| auto_download   | false        | Download every song you play; so that the same song can be played directly without loading again & again          |
| search_timeout  | 20           | Seconds before search gives up     |

## License

[MIT](https://github.com/lamsal27/music-cli/blob/main/LICENSE)
