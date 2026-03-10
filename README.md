# Music CLI - YouTube Integrated Minimal Music Player

A lightweight, efficient command-line music player with offline support, queue management, and playlist functionality. Designed for seamless music playback with minimal dependencies.

## Features

✨ **Core Functionality**
- 🎵 Play music from YouTube (online and offline)
- 📥 Download tracks for offline playback
- 🎒 Persistent queue across sessions
- 📚 Create and manage playlists
- 🔍 Search both local and online simultaneously
- 📊 Playback history tracking
- 🎚️ Customizable audio quality and format

✨ **Advanced Features**
- Direct CLI commands for quick operations
- Local file detection (auto-discovers music files in folder)
- SQLite database for efficient data management
- Configurable audio player and quality settings
- Lazy download on queue playback

## Installation

### Requirements
- Python 3.8+
- `mpv` (audio player)
- `yt-dlp` (YouTube downloader)
- `typer`, `rich` (Python libraries)

### Setup on Linux/macOS
```bash
# Install system dependencies
brew install mpv yt-dlp  # macOS
sudo apt install mpv     # Ubuntu/Debian
pip install yt-dlp       # Install yt-dlp via pip if needed

# Install Python dependencies
pip install typer rich

# Run the program
python music.py
```

### Setup on Windows
```bash
# Install mpv from: https://mpv.io/installation/
# Install yt-dlp
pip install yt-dlp

# Install Python dependencies
pip install typer rich

# Run the program
python music.py
```

## First Time Setup

On first run, the program will prompt you to specify a folder where music files will be saved:

```
╔─────────────────────────────────────────────────────╗
║           Welcome to Music CLI                      ║
║                                                     ║
║  Please specify the folder where music files       ║
║  will be saved.                                    ║
╚─────────────────────────────────────────────────────╝

Enter music folder path: ~/Music
✓  Music folder set to: /Users/username/Music
```

The program will create `config.json` in the script directory to remember your settings.

## File Structure

```
music-cli/
├── music.py              # Main application
├── config.json           # Configuration file (created on first run)
├── music.db              # SQLite database with songs, playlists, queue
├── README.md             # This file
└── ~/Music/              # Your music folder (customizable)
```

## Usage

### Interactive Menu Mode

Simply run the program without arguments:

```bash
python music.py
```

This opens the main menu:

```
Database: 45 songs (32 offline)
Size of directory: 156.3MB
Queue: 3 songs

(1)  Search Track
(2)  Library
(3)  Queue
(4)  History
(5)  Settings
(0)  Exit

 ==> Choose an option:
```

### Menu Options

#### (1) Search Track
Search for and play music from YouTube or your library.

```
Enter song name or artist: Taylor Swift Blank Space
⌕  Searching...

┌─ Search Results ────────────────────────────────────┐
│ Index │ Title                │ Type        │ Duration │
├───────┼──────────────────────┼─────────────┼──────────┤
│ 1     │ Blank Space          │ ⊘ Offline   │ 03:51    │
│ 2     │ Blank Space (Audio)  │ ◈ Online    │ 03:51    │
│ 3     │ Blank Space Cover    │ ◈ Online    │ 04:12    │
└─────────────────────────────────────────────────────┘

Play      Play song
Add       Add to queue
Download  Download song

(For example: play 1 => play the 1st song, add 2 => add 2nd song to queue, download 3 => download 3rd song)
Enter your choice (action index): play 1
▶  Playing: Blank Space
```

**Actions:**
- `play [number]` - Download and play the selected song
- `add [number]` - Add to queue without downloading
- `download [number]` - Download for offline playback

#### (2) Library
Browse and manage your downloaded songs and playlists.

**Sub-menu options:**
- View Downloaded Songs - List and play all music files in your folder
- Create Playlist - Create a new playlist
- View Playlists - Manage existing playlists
- Play Entire Playlist - Queue all songs from a playlist

#### (3) Queue
View and manage your playback queue.

```
┌─ Queue (5 songs) ───────────────────────────────────┐
│ Index │ Title              │ Artist           │
├───────┼────────────────────┼──────────────────┤
│ 1     │ Song One           │ Artist A         │
│ 2     │ Song Two           │ Artist B         │
│ 3     │ Song Three         │ Artist C         │
└─────────────────────────────────────────────────────┘

(1)  Play Queue
(2)  Remove Song
(3)  Clear Queue
(0)  Back

Select option: 1
```

**Queue Features:**
- Persistent across sessions
- Play entire queue sequentially
- Remove individual songs
- Clear all songs

#### (4) History
View your recently played tracks.

```
┌─ Playback History (Last 20) ────────────────────────┐
│ Index │ Date             │ Title        │ Artist    │
├───────┼──────────────────┼──────────────┼───────────┤
│ 1     │ 2024-03-05 14:32 │ Song Title   │ Artist    │
│ 2     │ 2024-03-05 14:10 │ Another Song │ Artist    │
└─────────────────────────────────────────────────────┘

Play      Play song
Add       Add to queue

Enter your choice (action index): play 1
```

#### (5) Settings
Configure application behavior.

```
╔─ SETTINGS ──────────────────────────────────────────╗
║              Configuration                          ║
╚─────────────────────────────────────────────────────╝

(1)  Download Directory
(2)  Audio Format
(3)  Audio Quality
(4)  Search Limit
(5)  Auto Download
(6)  View All Settings
(0)  Back

Select option: 1
```

**Settings:**
1. **Download Directory** - Change where music is saved
2. **Audio Format** - `mp3`, `m4a`, `wav`
3. **Audio Quality** - `bestaudio`, `worst`, `192`, `320` (kbps)
4. **Search Limit** - Number of results per search (default: 10)
5. **Auto Download** - Download on play or stream (default: True)
6. **View All Settings** - Display current configuration

---

### Command Line Mode

Use direct commands without entering the interactive menu:

#### Play Command
Search YouTube, show results table, download and play first result, then exit:

```bash
python music.py play "Taylor Swift Blank Space"
```

Output:
```
⌕  Searching...

┌─ Search Results ────────────────────────────────────┐
│ Index │ Title                │ Type        │ Duration │
├───────┼──────────────────────┼─────────────┼──────────┤
│ 1     │ Blank Space          │ ◈ Online    │ 03:51    │
│ 2     │ Blank Space (Audio)  │ ◈ Online    │ 03:51    │
└─────────────────────────────────────────────────────┘

▶  Playing: Blank Space
```

#### Download Command
Download the first search result without playing:

```bash
python music.py download "Adele Someone Like You"
```

Output:
```
⌕  Searching...
⬇  Downloading: Someone Like You...
✓  Downloaded: Someone Like You
```

#### Queue Command
Add the first search result to queue without showing table:

```bash
python music.py queue "Ed Sheeran Shape of You"
```

Output:
```
⌕  Searching...
✓  Added to queue: Shape of You
```

---

## Advanced Features

### Playlist Management

**Create Playlist:**
1. Go to Library → Create Playlist
2. Enter playlist name
3. Select "View Playlists" → Your Playlist → Add Song
4. Choose songs from your library (supports multi-select)

**Multi-Select Format:**
- Space-separated: `1 3 5` (adds songs 1, 3, and 5)
- Range format: `1-5` (adds songs 1 through 5)
- Combined: `1 3-5 7` (adds 1, 3, 4, 5, and 7)

**Play Playlist:**
1. Go to Library → Play Entire Playlist
2. Select a playlist
3. All songs queue automatically

### Local File Support

The program automatically detects music files in your music folder:
- Supported formats: `.mp3`, `.m4a`, `.wav`, `.flac`, `.ogg`, `.wma`
- Untracked files appear alongside downloaded songs
- Play or queue local files directly

### Queue Persistence

Your queue is automatically saved and restored when you:
- Exit and restart the program
- Add/remove songs
- Play songs

### Search Optimization

- **Simultaneous search** checks both local library and YouTube
- Offline songs appear first
- Duplicate titles are filtered
- Results show song type (offline ⊘ or online ◈)

---

## Configuration File

`config.json` stores your settings:

```json
{
  "download_dir": "/Users/username/Music",
  "audio_format": "mp3",
  "audio_quality": "bestaudio",
  "player": "mpv",
  "search_limit": 10,
  "auto_download": true,
  "search_timeout": 20
}
```

Edit manually to change defaults, or use the Settings menu.

---

## Database

`music.db` is a SQLite database containing:

- **songs** - All tracks with metadata
- **playlists** - Your custom playlists
- **playlist_songs** - Playlist contents
- **queue** - Persistent queue

You can inspect it with any SQLite viewer:
```bash
sqlite3 music.db ".tables"
sqlite3 music.db "SELECT title, uploader FROM songs LIMIT 5;"
```

---

## Troubleshooting

### "No such command 'play'"
Ensure you're using the correct syntax:
```bash
python music.py play "song name"  # ✓ Correct
python music.py play              # ✗ Missing song name
```

### Music folder not created
Check that your specified path is valid and you have write permissions:
```bash
mkdir -p ~/Music
python music.py
```

### yt-dlp errors
Update to the latest version:
```bash
pip install --upgrade yt-dlp
```

### mpv not found
Install mpv from https://mpv.io/installation/

### Config corrupted
Delete `config.json` and restart. You'll be prompted for music folder again.

---

## Tips & Tricks

🎯 **Quick Play**
```bash
python music.py play "artist - song name"
```

🎯 **Batch Download**
Use the menu to add multiple songs to queue, then play.

🎯 **Search Tips**
- Search by artist: `Taylor Swift`
- Search by song: `Blank Space`
- Search with both: `Taylor Swift Blank Space` (more accurate)

🎯 **Quality Settings**
- `bestaudio` - Best available quality (larger file)
- `192` - 192 kbps (balanced)
- `320` - 320 kbps (high quality)
- `worst` - Fastest download

---

## License

MIT License - Free to use and modify

## Support

For issues or suggestions, check:
1. This README
2. The help.txt file included
3. Application error messages

---

**Happy listening! 🎵**
