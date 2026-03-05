import os
import subprocess
import json
import shutil
import sys
import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent

console = Console()


class ConfigManager:
    """Manages configuration with JSON (settings only)."""
    
    def __init__(self):
        self.config_path = SCRIPT_DIR / "config.json"
        self.defaults = {
            "download_dir": None,  # Will be set on first run
            "audio_format": "mp3",
            "audio_quality": "bestaudio",
            "player": "mpv",
            "search_limit": 10,
            "auto_download": False,
            "search_timeout": 20
        }
        self.config = self.load()
        self._init_first_run()

    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    merged = self.defaults.copy()
                    merged.update(loaded)
                    return merged
            except json.JSONDecodeError:
                console.print(f"⚠  Config corrupted, using defaults", style="bold yellow")
                return self.defaults.copy()
        return self.defaults.copy()

    def _init_first_run(self):
        """Prompt for music folder on first run."""
        if not self.config_path.exists():
            os.system("cls" if os.name == "nt" else "clear")
            console.print(Panel(
                "[bold cyan]Welcome to Music CLI[/]\n\n"
                "Please specify the folder where music files will be saved.",
                title="First Time Setup",
                style="bold blue"
            ))
            console.print()
            
            while True:
                music_dir = typer.prompt("Enter music folder path")
                music_path = Path(music_dir).expanduser().resolve()
                
                try:
                    music_path.mkdir(parents=True, exist_ok=True)
                    console.print(f"✓  Music folder set to: {music_path}", style="bold green")
                    self.config["download_dir"] = str(music_path)
                    self.save()
                    break
                except Exception as e:
                    console.print(f"✘  Invalid path: {str(e)}", style="bold red")
                    console.print("Please try again.")

    def save(self):
        """Persist configuration."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve configuration value."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value and persist."""
        if key in self.defaults:
            self.config[key] = value
            self.save()
        else:
            console.print(f"✘  Unknown setting: {key}", style="bold red")


class SongDatabase:
    """Song database using SQLite for efficiency and persistence."""
    
    def __init__(self):
        self.db_path = SCRIPT_DIR / "music.db"
        self.init_db()

    def init_db(self):
        """Initialize SQLite database with proper schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    url_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    uploader TEXT,
                    duration_seconds INTEGER,
                    local_path TEXT,
                    is_downloaded INTEGER DEFAULT 0,
                    played_at TEXT,
                    last_played TEXT,
                    play_count INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_song(self, url: str, title: str, uploader: str, duration: int, local_path: Optional[str] = None):
        """Add or update song in database."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM songs WHERE url_hash = ?', (url_hash,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE songs 
                    SET last_played = ?, play_count = play_count + 1
                    WHERE url_hash = ?
                ''', (now, url_hash))
            else:
                cursor.execute('''
                    INSERT INTO songs 
                    (url, url_hash, title, uploader, duration_seconds, local_path, is_downloaded, played_at, last_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, url_hash, title, uploader, duration, local_path, 1 if local_path else 0, now, now))
            conn.commit()

    def search_local(self, query: str) -> List[Dict[str, Any]]:
        """Search database by title."""
        query_lower = f"%{query.lower()}%"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM songs WHERE LOWER(title) LIKE ? ORDER BY last_played DESC',
                (query_lower,)
            )
            results = [dict(row) for row in cursor.fetchall()]
        return results

    def get_downloaded_songs(self) -> List[Dict[str, Any]]:
        """Get all downloaded songs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM songs WHERE is_downloaded = 1 AND local_path IS NOT NULL ORDER BY last_played DESC'
            )
            results = [dict(row) for row in cursor.fetchall()]
        return [s for s in results if Path(s['local_path']).exists()] if results else []

    def get_all_songs(self) -> List[Dict[str, Any]]:
        """Get all songs in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM songs ORDER BY last_played DESC')
            results = [dict(row) for row in cursor.fetchall()]
        return results

    def get_song_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get song by URL."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM songs WHERE url = ?', (url,))
            result = cursor.fetchone()
        return dict(result) if result else None


class PlaylistManager:
    """Manages playlists using SQLite."""
    
    def __init__(self):
        self.db_path = SCRIPT_DIR / "music.db"
        self.init_db()

    def init_db(self):
        """Initialize playlist tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                    UNIQUE(playlist_id, url)
                )
            ''')
            conn.commit()

    def create_playlist(self, name: str) -> bool:
        """Create new playlist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('INSERT INTO playlists (name) VALUES (?)', (name,))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def add_song_to_playlist(self, playlist: str, url: str, title: str) -> bool:
        """Add song to playlist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM playlists WHERE name = ?', (playlist,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                playlist_id = result[0]
                cursor.execute(
                    'INSERT INTO playlist_songs (playlist_id, url, title) VALUES (?, ?, ?)',
                    (playlist_id, url, title)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_song_from_playlist(self, playlist: str, url: str) -> bool:
        """Remove song from playlist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM playlists WHERE name = ?', (playlist,))
            result = cursor.fetchone()
            if not result:
                return False
            
            playlist_id = result[0]
            cursor.execute('DELETE FROM playlist_songs WHERE playlist_id = ? AND url = ?', (playlist_id, url))
            conn.commit()
        return cursor.rowcount > 0

    def delete_playlist(self, name: str) -> bool:
        """Delete playlist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM playlists WHERE name = ?', (name,))
            conn.commit()
        return cursor.rowcount > 0

    def get_playlists(self) -> List[str]:
        """Get all playlist names."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM playlists ORDER BY created_at DESC')
            results = cursor.fetchall()
        return [r[0] for r in results]

    def get_playlist_songs(self, name: str) -> List[Dict[str, Any]]:
        """Get songs in playlist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ps.url, ps.title 
                FROM playlist_songs ps
                JOIN playlists p ON ps.playlist_id = p.id
                WHERE p.name = ?
                ORDER BY ps.position, ps.added_at
            ''', (name,))
            results = [dict(row) for row in cursor.fetchall()]
        return results


class QueueManager:
    """Manages persistent playback queue using SQLite."""
    
    def __init__(self):
        self.db_path = SCRIPT_DIR / "music.db"
        self.init_db()
        self.queue = self.load_queue()
        self.current_index = 0

    def init_db(self):
        """Initialize queue table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    uploader TEXT,
                    duration_seconds INTEGER,
                    position INTEGER,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT url, title, uploader, duration_seconds FROM queue ORDER BY position')
            results = [dict(row) for row in cursor.fetchall()]
        return results

    def add_to_queue(self, song: Dict[str, Any]):
        """Add song to queue."""
        self.queue.append(song)
        self._persist_queue()

    def add_multiple_to_queue(self, songs: List[Dict[str, Any]]):
        """Add multiple songs to queue."""
        self.queue.extend(songs)
        self._persist_queue()

    def remove_from_queue(self, index: int) -> bool:
        """Remove song from queue."""
        if 0 <= index < len(self.queue):
            self.queue.pop(index)
            self._persist_queue()
            return True
        return False

    def clear_queue(self):
        """Clear entire queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM queue')
            conn.commit()
        self.queue = []
        self.current_index = 0

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get current queue."""
        return self.queue

    def _persist_queue(self):
        """Save queue to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM queue')
            for idx, song in enumerate(self.queue):
                conn.execute(
                    'INSERT INTO queue (url, title, uploader, duration_seconds, position) VALUES (?, ?, ?, ?, ?)',
                    (song.get('url'), song.get('title'), song.get('uploader'), song.get('duration_seconds'), idx)
                )
            conn.commit()

    def peek_next(self) -> Optional[Dict[str, Any]]:
        """Get next song without removing."""
        if self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def advance(self) -> Optional[Dict[str, Any]]:
        """Advance to next song."""
        if self.current_index < len(self.queue) - 1:
            self.current_index += 1
            return self.queue[self.current_index]
        return None

    def is_queue_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self.queue) == 0


class DependencyValidator:
    """Validates system dependencies."""
    
    required_commands = ["yt-dlp", "mpv"]

    @staticmethod
    def check_command(command: str) -> bool:
        """Check if command exists in PATH."""
        return shutil.which(command) is not None

    @classmethod
    def validate_all(cls) -> bool:
        """Validate all dependencies."""
        missing = []
        for cmd in cls.required_commands:
            if not cls.check_command(cmd):
                missing.append(cmd)
        
        if missing:
            console.print(
                f"✘  Missing: {', '.join(missing)}",
                style="bold red"
            )
            console.print(
                Panel(
                    f"Install from: https://mpv.io/ and pip install yt-dlp",
                    title="Installation",
                    style="yellow"
                )
            )
            return False
        return True


class MusicPlayer:
    """Music player with offline-first, simultaneous search."""
    
    def __init__(self, config: ConfigManager, db: SongDatabase):
        self.config = config
        self.db = db
        self.player = config.get("player")
        self.download_dir = Path(config.get("download_dir"))
        self.audio_format = config.get("audio_format")
        self.auto_download = config.get("auto_download")
        self._init_data_dir()

    def _init_data_dir(self):
        """Initialize download directory."""
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str, style: str = ""):
        """Log messages to console."""
        if style:
            console.print(message, style=style)
        else:
            console.print(message)

    def search_simultaneous(self, query: str, limit: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Search offline and online simultaneously."""
        offline_results = self.db.search_local(query)
        online_results = self._search_youtube(query, limit)
        return offline_results, online_results

    def _search_youtube(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search YouTube."""
        try:
            result = subprocess.check_output(
                [
                    "yt-dlp",
                    f"ytsearch{limit}:{query}",
                    "--flat-playlist",
                    "-J",
                    "--no-warnings"
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=self.config.get("search_timeout")
            )
            data = json.loads(result)
            return data.get("entries", [])
        except:
            return []

    def download(self, url: str, title: str) -> Optional[str]:
        """Download audio file."""
        try:
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            local_filename = f"{safe_title}.{self.audio_format}"
            output_path = self.download_dir / local_filename
            
            if output_path.exists():
                self._log(f"◆  Already cached: {safe_title}", "")
                return str(output_path)

            self._log(f"⬇  Downloading: {safe_title}", "")

            cmd = [
                "yt-dlp",
                "-f", self.config.get("audio_quality"),
                "--extract-audio",
                "--audio-format", self.audio_format,
                "-o", str(output_path),
                url
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=300
            )

            if result.returncode == 0 and output_path.exists():
                self._log(f"✓  Downloaded: {safe_title}", "")
                return str(output_path)
            else:
                self._log(f"✘  Download failed", "bold red")
                return None

        except Exception as e:
            self._log(f"✘  {str(e)}", "bold red")
            return None

    def _is_downloaded(self, url: str) -> Optional[str]:
        """Check if URL is downloaded (FIXED: checks actual file existence)."""
        entry = self.db.get_song_by_url(url)
        if entry and entry.get("local_path"):
            local_path = entry["local_path"]
            if Path(local_path).exists():
                return local_path
        return None

    def play(self, url: str, title: str, uploader: str = "Unknown", duration: int = 0) -> bool:
        """Play audio track."""
        try:
            local_path = self._is_downloaded(url)
            
            if not local_path and self.auto_download:
                local_path = self.download(url, title)
                if not local_path:
                    return False
            
            is_offline = Path(local_path).exists() if local_path and not local_path.startswith("http") else False
            mode = f"⊘ (offline)" if is_offline else f"◈ (streaming)"
            
            self._log(f"▶  Playing: {title} {mode}", "")
            
            self.db.add_song(url, title, uploader, duration, local_path if is_offline else None)
            
            play_path = local_path or self._get_stream_url(url)
            if not play_path:
                self._log(f"✘  Could not get playback URL", "bold red")
                return False
            
            subprocess.run(
                [self.player, "--no-cache", "--log-file=/dev/null", "--no-config", play_path],
                check=False,
                timeout=None
            )
            return True

        except Exception as e:
            self._log(f"✘  {str(e)}", "bold red")
            return False

    def _get_stream_url(self, url: str) -> Optional[str]:
        """Get streaming URL."""
        try:
            output = subprocess.check_output(
                ["yt-dlp", "-f", self.config.get("audio_quality"), "-g", url],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10
            ).strip()
            return output
        except:
            return None

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = 0
        file_count = 0
        
        if self.download_dir.exists():
            for file in self.download_dir.iterdir():
                if file.is_file():
                    file_count += 1
                    total_size += file.stat().st_size
        
        return {
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "directory": str(self.download_dir)
        }


def queue_menu(queue: QueueManager, player: MusicPlayer, db: SongDatabase):
    """View and play queued songs with online-only queueing and lazy download."""
    queued_songs = queue.get_queue()
    
    if not queued_songs:
        console.print(f"ℹ  Queue is empty", style="dim")
        input("Press Enter...")
        return
    
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        table = Table(
            title=f"Queue ({len(queued_songs)} songs)",
            show_header=True,
            header_style="bold cyan"
        )

        table.add_column("Index", style="cyan", width=5)
        table.add_column("Title", style="green", overflow="ellipsis", max_width=70)
        table.add_column("Artist", style="magenta", max_width=20)

        for idx, song in enumerate(queued_songs, 1):
            table.add_row(str(idx), song.get('title', 'Unknown'), song.get('uploader', 'Unknown'))

        console.print(table)
        console.print()
        
        action_table = Table(show_header=False, box=None)
        action_table.add_column(style="cyan", width=4)
        action_table.add_column()
        action_table.add_row("(1)", "Play Queue")
        action_table.add_row("(2)", "Remove Song")
        action_table.add_row("(3)", "Clear Queue")
        action_table.add_row("(0)", "Back")
        
        console.print(action_table)
        console.print()
        
        choice = typer.prompt("Select option", default="0")
        
        if choice == "1":
            play_queue(queue, player)
            break
        elif choice == "2":
            idx = typer.prompt("Song index to remove (0 to skip)", default="0", type=int)
            if 1 <= idx <= len(queued_songs):
                queue.remove_from_queue(idx - 1)
                queued_songs = queue.get_queue()
                console.print(f"✓  Removed!", style="bold green")
                input("Press Enter...")
        elif choice == "3":
            queue.clear_queue()
            console.print(f"✓  Queue cleared!", style="bold green")
            input("Press Enter...")
            break
        elif choice == "0":
            break
        else:
            console.print(f"✘  Invalid option", style="bold red")
            input("Press Enter...")


def play_queue(queue: QueueManager, player: MusicPlayer):
    """Play all songs in queue with lazy download for online songs."""
    queued_songs = queue.get_queue()
    
    if not queued_songs:
        console.print(f"ℹ  Queue is empty", style="dim")
        input("Press Enter...")
        return
    
    for song in queued_songs:
        url = song.get('url')
        title = song.get('title', 'Unknown')
        uploader = song.get('uploader', 'Unknown')
        duration = song.get('duration_seconds', 0)
        
        player.play(url, title, uploader, duration)


def show_main_menu(config: ConfigManager, player: MusicPlayer, db: SongDatabase, playlists: PlaylistManager, queue: QueueManager):
    """Display main menu with enhanced UI."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        cache_info = player.get_cache_info()
        db_songs = len(db.get_all_songs())
        downloaded_songs = len(db.get_downloaded_songs())
        queue_size = len(queue.get_queue())
        


        console.print(f"\n  Database: {db_songs} songs ({downloaded_songs} offline)")
        console.print(f"  Size of directory: {cache_info['total_size_mb']}MB")
        console.print(f"  Queue: {queue_size} songs\n")
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=4)

        table.add_column()
        
        table.add_row("(1)", "Search Track")
        table.add_row("(2)", "Library")
        table.add_row("(3)", "Queue")
        table.add_row("(4)", "History")
        table.add_row("(5)", "Settings")
        table.add_row("(0)", "Exit")
        
        console.print(table)
        console.print()
        
        choice = typer.prompt(" ==> Choose an option")
        
        if choice == "1":
            play_menu(player, config, queue, db)
        elif choice == "2":
            library_menu(db, playlists, player, queue)
        elif choice == "3":
            queue_menu(queue, player, db)
        elif choice == "4":
            history_menu(db, player, queue)
        elif choice == "5":
            settings_menu(config, player)
        elif choice == "0":
            console.print(f"ℹ  Farewell, Master.", style="dim")
            raise typer.Exit(0)
        else:
            console.print(f"✘  Invalid option", style="bold red")
            input("Press Enter...")


def play_menu(player: MusicPlayer, config: ConfigManager, queue: QueueManager, db: SongDatabase):
    """Play menu with simultaneous search and download option."""
    query = typer.prompt("\n  Enter song name or artist")
    
    if not query:
        return
    
    console.print(f"⌕  Searching...")
    offline_results, online_results = player.search_simultaneous(query, limit=config.get("search_limit"))
    
    os.system("cls" if os.name == "nt" else "clear")
    table = Table(
        title="Search Results",
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Duration", style="yellow", width=10)

    def format_time(seconds: int) -> str:
        seconds = int(seconds) if seconds else 0
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    idx = 1
    combined_results = []
    seen_titles = set()
    
    for result in offline_results:
        if result.get('title') not in seen_titles:
            table.add_row(
                str(idx),
                result.get('title', 'Unknown'),
                f"⊘ Offline",
                format_time(result.get('duration_seconds', 0))
            )
            combined_results.append(result)
            seen_titles.add(result.get('title'))
            idx += 1
    
    for result in online_results:
        title = result.get('title', 'Unknown')
        if title not in seen_titles:
            table.add_row(
                str(idx),
                title,
                f"◈ Online",
                format_time(result.get('duration', 0))
            )
            combined_results.append(result)
            seen_titles.add(title)
            idx += 1

    console.print(table)
    console.print()
    
    # Display action menu
    action_table = Table(show_header=False, box=None)
    action_table.add_column(style="cyan", width=8)
    action_table.add_column()
    
    action_table.add_row("Play", "Play song")
    action_table.add_row("Add", "Add to queue")
    action_table.add_row("Download", "Download song")

    console.print(action_table)
    console.print()
   
    console.print("(For example: play 1 => play the 1st song, add 2 => add 2nd song to queue, download 3 => download 3rd song)\n")
    console.print("Enter your choice (action index)", end="")
    user_input = typer.prompt("").strip()
    
    if not user_input:
        console.print(f"  Invalid input", style="bold red")
        input("Press Enter...")
        return
    
    try:
        parts = user_input.split()
        if len(parts) != 2:
            console.print(f"  Invalid format. Use: action index (e.g., play 1 or add 2)", style="bold red")
            input("Press Enter...")
            return
        
        action = parts[0].lower()
        choice = int(parts[1])
        
        if not (1 <= choice <= len(combined_results)):
            console.print(f"  Invalid selection", style="bold red")
            input("Press Enter...")
            return
        
        result = combined_results[choice - 1]
        
        if 'url' in result:
            url = result['url']
        else:
            url = f"https://www.youtube.com/watch?v={result.get('id')}"
        
        title = result.get('title', 'Unknown')
        uploader = result.get('uploader', 'Unknown')
        duration = result.get('duration_seconds') or result.get('duration', 0)
        
        if action == 'play' or action == 'p':
            player.play(url, title, uploader, duration)
        elif action == 'add' or action == 'queue' or action == 'q':
            queue.add_to_queue({"url": url, "title": title, "uploader": uploader, "duration_seconds": duration})
            console.print(f"✓  Added to queue!", style="bold green")
        elif action == 'download' or action == 'd':
            if player.download(url, title):
                console.print(f"✓  Downloaded: {title}", style="bold green")
                local_path = player.download_dir / f"{title}.{player.audio_format}"
                db.add_song(url, title, uploader, duration, str(local_path))
            else:
                console.print(f"✘  Download failed", style="bold red")
        else:
            console.print(f"  Invalid action. Use 'play', 'add', or 'download'", style="bold red")
    
    except ValueError:
        console.print(f"  Invalid input format", style="bold red")
    
    input("Press Enter...")




def library_menu(db: SongDatabase, playlists: PlaylistManager, player: MusicPlayer, queue: QueueManager):
    """Offline library with playlists."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        downloaded = db.get_downloaded_songs()
        playlist_list = playlists.get_playlists()
        
        console.print(Panel(
            f"[bold cyan]OFFLINE LIBRARY[/]\n\n"
            f"📄 Downloaded Songs: {len(downloaded)}\n"
            f"📁 Playlists: {len(playlist_list)}",
            title="Library",
            style="bold blue"
        ))
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=4)
        table.add_column()
        
        table.add_row("(1)", "View Downloaded Songs")
        table.add_row("(2)", "Create Playlist")
        table.add_row("(3)", "View Playlists")
        table.add_row("(4)", "Play Entire Playlist")
        table.add_row("(0)", "Back")
        
        console.print(table)
        console.print()
        
        choice = typer.prompt("Select option", default="0")
        
        if choice == "1":
            view_downloaded_songs(downloaded, player, queue, db)
        elif choice == "2":
            create_playlist_prompt(playlists)
        elif choice == "3":
            view_playlists_menu(playlists, db, player, queue)
        elif choice == "4":
            play_playlist(playlists, db, player, queue)
        elif choice == "0":
            break
        else:
            console.print(f"✘  Invalid option", style="bold red")
            input("Press Enter...")


def get_local_music_files(player: MusicPlayer, db: SongDatabase) -> List[Dict[str, Any]]:
    """Get all music files from download directory including untracked files."""
    music_files = []
    music_dir = player.download_dir
    
    if not music_dir.exists():
        return music_files
    
    # Get all audio files from directory
    audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.ogg', '.wma')
    
    for file in music_dir.iterdir():
        if file.is_file() and file.suffix.lower() in audio_extensions:
            # Check if already in database
            db_entry = None
            if file.suffix.lower() == '.mp3':
                # Try to find in database
                song_list = db.get_all_songs()
                for song in song_list:
                    if song.get('local_path') == str(file):
                        db_entry = song
                        break
            
            if db_entry:
                music_files.append(db_entry)
            else:
                # Create entry for untracked file
                music_files.append({
                    'url': None,
                    'title': file.stem,
                    'uploader': 'Local File',
                    'duration_seconds': 0,
                    'local_path': str(file),
                    'is_downloaded': 1
                })
    
    return music_files


def view_downloaded_songs(songs: List[Dict[str, Any]], player: MusicPlayer, queue: QueueManager, db: SongDatabase):
    """View and play downloaded songs including untracked local files."""
    # Get all local files including untracked ones
    all_files = get_local_music_files(player, db)
    
    if not all_files:
        console.print(f"ℹ  No music files in library", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(
        title=f"Downloaded Songs & Local Files ({len(all_files)})",
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)
    table.add_column("Artist", style="magenta", max_width=25)

    for idx, song in enumerate(all_files, 1):
        table.add_row(str(idx), song.get('title', 'Unknown'), song.get('uploader', 'Unknown'))

    console.print(table)
    console.print()
    
    action_table = Table(show_header=False, box=None)
    action_table.add_column(style="cyan", width=8)
    action_table.add_column()
    
    action_table.add_row("Play", "Play song")
    action_table.add_row("Add", "Add to queue")

    console.print(action_table)
    console.print()
    
    console.print("(For example: play 1 => play the 1st song, add 2 => add 2nd song to queue)\n")
    console.print("Enter your choice (action index)", end="")
    user_input = typer.prompt("").strip()
    
    if not user_input:
        input("Press Enter...")
        return
    
    try:
        parts = user_input.split()
        if len(parts) != 2:
            console.print(f"  Invalid format. Use: action index", style="bold red")
            input("Press Enter...")
            return
        
        action = parts[0].lower()
        choice = int(parts[1])
        
        if not (1 <= choice <= len(all_files)):
            console.print(f"  Invalid selection", style="bold red")
            input("Press Enter...")
            return
        
        song = all_files[choice - 1]
        
        if action == 'play' or action == 'p':
            player.play(song['url'] or song['local_path'], song['title'], song.get('uploader', 'Unknown'), song.get('duration_seconds', 0))
        elif action == 'add' or action == 'queue' or action == 'q':
            queue.add_to_queue({"url": song['url'] or song['local_path'], "title": song['title'], "uploader": song.get('uploader', 'Unknown'), "duration_seconds": song.get('duration_seconds', 0)})
            console.print(f"✓  Added to queue!", style="bold green")
        else:
            console.print(f"  Invalid action. Use 'play' or 'add'", style="bold red")
    
    except ValueError:
        console.print(f"  Invalid input format", style="bold red")
    
    input("Press Enter...")


def create_playlist_prompt(playlists: PlaylistManager):
    """Create new playlist."""
    name = typer.prompt("Playlist name")
    
    if playlists.create_playlist(name):
        console.print(f"✓  Playlist created!", style="bold green")
    else:
        console.print(f"✘  Playlist already exists", style="bold red")
    
    input("Press Enter...")


def view_playlists_menu(playlists: PlaylistManager, db: SongDatabase, player: MusicPlayer, queue: QueueManager):
    """View and manage playlists."""
    playlist_list = playlists.get_playlists()
    
    if not playlist_list:
        console.print(f"ℹ  No playlists created", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    console.print(Panel(
        "[bold cyan]PLAYLISTS[/]",
        title="Library",
        style="bold blue"
    ))
    
    table = Table(show_header=False, box=None)
    table.add_column(style="cyan", width=4)
    table.add_column()
    
    for idx, playlist in enumerate(playlist_list, 1):
        songs_count = len(playlists.get_playlist_songs(playlist))
        table.add_row(f"({idx})", f"{playlist} ({songs_count} songs)")
    
    console.print(table)
    console.print()
    
    choice = typer.prompt("Select playlist (0 to skip)", default="0", type=int)
    
    if 1 <= choice <= len(playlist_list):
        playlist_name = playlist_list[choice - 1]
        manage_playlist(playlist_name, playlists, db, player)
    
    input("Press Enter...")


def manage_playlist(playlist_name: str, playlists: PlaylistManager, db: SongDatabase, player: MusicPlayer):
    """Manage specific playlist."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        songs = playlists.get_playlist_songs(playlist_name)
        
        console.print(Panel(
            f"[bold cyan]{playlist_name}[/]\n\n"
            f"📄 Songs: {len(songs)}",
            title="Playlist",
            style="bold blue"
        ))
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=4)
        table.add_column()
        
        table.add_row("(1)", "View Songs")
        table.add_row("(2)", "Add Song")
        table.add_row("(3)", "Remove Song")
        table.add_row("(4)", "Delete Playlist")
        table.add_row("(0)", "Back")
        
        console.print(table)
        console.print()
        
        choice = typer.prompt("Select option", default="0")
        
        if choice == "1":
            view_playlist_songs(playlist_name, playlists, player)
        elif choice == "2":
            add_song_to_playlist(playlist_name, playlists, db)
        elif choice == "3":
            remove_song_from_playlist(playlist_name, playlists)
        elif choice == "4":
            if playlists.delete_playlist(playlist_name):
                console.print(f"✓  Playlist deleted!", style="bold green")
                input("Press Enter...")
                break
        elif choice == "0":
            break
        else:
            console.print(f"✘  Invalid option", style="bold red")
            input("Press Enter...")


def view_playlist_songs(playlist_name: str, playlists: PlaylistManager, player: MusicPlayer):
    """View songs in playlist."""
    songs = playlists.get_playlist_songs(playlist_name)
    
    if not songs:
        console.print(f"ℹ  Playlist is empty", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(
        title=f"{playlist_name}",
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)

    for idx, song in enumerate(songs, 1):
        table.add_row(str(idx), song.get('title', 'Unknown'))

    console.print(table)
    
    choice = typer.prompt("Select song to play (0 to skip)", default="0", type=int)
    
    if 1 <= choice <= len(songs):
        song = songs[choice - 1]
        player.play(song['url'], song['title'])
    
    input("Press Enter...")


def add_song_to_playlist(playlist_name: str, playlists: PlaylistManager, db: SongDatabase):
    """Add song to playlist."""
    downloaded = db.get_downloaded_songs()
    
    if not downloaded:
        console.print(f"ℹ  No downloaded songs available", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(
        title="Downloaded Songs",
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)

    for idx, song in enumerate(downloaded, 1):
        table.add_row(str(idx), song.get('title', 'Unknown'))

    console.print(table)
    
    choice = typer.prompt("Select song (0 to skip)", default="0", type=int)
    
    if 1 <= choice <= len(downloaded):
        song = downloaded[choice - 1]
        if playlists.add_song_to_playlist(playlist_name, song['url'], song['title']):
            console.print(f"✓  Added to playlist!", style="bold green")
        else:
            console.print(f"✘  Failed to add", style="bold red")
    
    input("Press Enter...")


def remove_song_from_playlist(playlist_name: str, playlists: PlaylistManager):
    """Remove song from playlist."""
    songs = playlists.get_playlist_songs(playlist_name)
    
    if not songs:
        console.print(f"ℹ  Playlist is empty", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(
        title=f"{playlist_name}",
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)

    for idx, song in enumerate(songs, 1):
        table.add_row(str(idx), song.get('title', 'Unknown'))

    console.print(table)
    
    choice = typer.prompt("Select song to remove (0 to skip)", default="0", type=int)
    
    if 1 <= choice <= len(songs):
        song = songs[choice - 1]
        if playlists.remove_song_from_playlist(playlist_name, song['url']):
            console.print(f"✓  Removed from playlist!", style="bold green")
        else:
            console.print(f"✘  Failed to remove", style="bold red")
    
    input("Press Enter...")


def play_playlist(playlists: PlaylistManager, db: SongDatabase, player: MusicPlayer, queue: QueueManager):
    """Play entire playlist."""
    playlist_list = playlists.get_playlists()
    
    if not playlist_list:
        console.print(f"ℹ  No playlists", style="dim")
        input("Press Enter...")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(show_header=False, box=None)
    table.add_column(style="cyan", width=4)
    table.add_column()
    
    for idx, playlist in enumerate(playlist_list, 1):
        songs_count = len(playlists.get_playlist_songs(playlist))
        table.add_row(f"({idx})", f"{playlist} ({songs_count} songs)")
    
    console.print(table)
    console.print()
    
    choice = typer.prompt("Select playlist (0 to skip)", default="0", type=int)
    
    if 1 <= choice <= len(playlist_list):
        playlist_name = playlist_list[choice - 1]
        songs = playlists.get_playlist_songs(playlist_name)
        
        for song in songs:
            queue.add_to_queue(song)
        
        console.print(f"✓  Added {len(songs)} songs to queue!", style="bold green")
    
    input("Press Enter...")



def history_menu(db: SongDatabase, player: MusicPlayer, queue: QueueManager):
    """History menu with play and queue options."""
    songs = db.get_all_songs()
    
    if not songs:
        console.print(f"ℹ  No history", style="dim")
        input("Press Enter...")
        return

    os.system("cls" if os.name == "nt" else "clear")
    
    table = Table(
        title=f"Playback History (Last 20)",
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Date", style="yellow", max_width=19)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=60)
    table.add_column("Artist", style="magenta", max_width=20)

    for idx, entry in enumerate(reversed(songs[-20:]), 1):
        try:
            played_dt = datetime.fromisoformat(entry.get("played", ""))
            date_str = played_dt.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = "Unknown"
        
        table.add_row(
            str(idx),
            date_str,
            entry.get("title", "Unknown"),
            entry.get("uploader", "Unknown")
        )

    console.print(table)
    console.print()
    
    table = Table(show_header=False, box=None)
    table.add_column(style="cyan", width=4)
    table.add_column()
    
    table.add_row("(1)", "Play Song")
    table.add_row("(2)", "Add to Queue")
    table.add_row("(0)", "Back")
    
    console.print(table)
    console.print()
    
    choice = typer.prompt("Select option", default="0")
    
    if choice == "1":
        idx = typer.prompt("Song index to play", default="0", type=int)
        if 1 <= idx <= 20:
            song = list(reversed(songs[-20:]))[idx - 1]
            player.play(song['url'], song['title'], song['uploader'], song.get('duration_seconds', 0))
    elif choice == "2":
        idx = typer.prompt("Song index to add", default="0", type=int)
        if 1 <= idx <= 20:
            song = list(reversed(songs[-20:]))[idx - 1]
            queue.add_to_queue(song)
            console.print(f"✓  Added to queue!", style="bold green")
    
    input("Press Enter...")



def settings_menu(config: ConfigManager, player: MusicPlayer):
    """Improved settings menu with essential options only."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        console.print(Panel(
            "[bold cyan]SETTINGS[/]",
            title="Configuration",
            style="bold blue"
        ))
        
        console.print()
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=4)
        table.add_column()
        
        table.add_row("(1)", "Download Directory")
        table.add_row("(2)", "Audio Format")
        table.add_row("(3)", "Audio Quality")
        table.add_row("(4)", "Search Limit")
        table.add_row("(5)", "Auto Download")
        table.add_row("(6)", "View All Settings")
        table.add_row("(0)", "Back")
        
        console.print(table)
        console.print()
        
        choice = typer.prompt("Select option", default="0")
        
        if choice == "1":
            new_dir = typer.prompt("New download directory")
            config.set("download_dir", new_dir)
            console.print(f"✓  Updated!", style="bold green")
            player.download_dir = Path(new_dir)
        elif choice == "2":
            format_choice = typer.prompt("Audio format (mp3/m4a/wav)")
            if format_choice in ("mp3", "m4a", "wav"):
                config.set("audio_format", format_choice)
                console.print(f"✓  Updated!", style="bold green")
                player.audio_format = format_choice
            else:
                console.print(f"✘  Invalid format", style="bold red")
        elif choice == "3":
            quality = typer.prompt("Audio quality (bestaudio/worst/192/320)")
            config.set("audio_quality", quality)
            console.print(f"✓  Updated!", style="bold green")
        elif choice == "4":
            limit = typer.prompt("Search result limit (number)", type=int)
            config.set("search_limit", limit)
            console.print(f"✓  Updated!", style="bold green")
        elif choice == "5":
            auto_dl = typer.prompt("Auto download on play? (true/false)")
            config.set("auto_download", auto_dl.lower() == "true")
            console.print(f"✓  Updated!", style="bold green")
            player.auto_download = config.get("auto_download")
        elif choice == "6":
            os.system("cls" if os.name == "nt" else "clear")
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")
            
            for k, v in config.config.items():
                table.add_row(k, str(v))
            
            console.print(table)
            input("Press Enter...")
        elif choice == "0":
            break
        else:
            console.print(f"✘  Invalid option", style="bold red")
        
        if choice not in ("6", "0"):
            input("Press Enter...")


def cli_play(player: MusicPlayer, config: ConfigManager, db: SongDatabase, queue: QueueManager, song_name: str):
    """CLI play command: show results table, download and play first result."""
    console.print(f"⌕  Searching...")
    offline_results, online_results = player.search_simultaneous(song_name, limit=config.get("search_limit"))
    
    if not offline_results and not online_results:
        console.print(f"✘  No results found", style="bold red")
        return
    
    os.system("cls" if os.name == "nt" else "clear")
    table = Table(
        title="Search Results",
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("Index", style="cyan", width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=70)
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Duration", style="yellow", width=10)

    def format_time(seconds: int) -> str:
        seconds = int(seconds) if seconds else 0
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    idx = 1
    combined_results = []
    seen_titles = set()
    
    for result in offline_results:
        if result.get('title') not in seen_titles:
            table.add_row(
                str(idx),
                result.get('title', 'Unknown'),
                f"⊘ Offline",
                format_time(result.get('duration_seconds', 0))
            )
            combined_results.append(result)
            seen_titles.add(result.get('title'))
            idx += 1
    
    for result in online_results:
        title = result.get('title', 'Unknown')
        if title not in seen_titles:
            table.add_row(
                str(idx),
                title,
                f"◈ Online",
                format_time(result.get('duration', 0))
            )
            combined_results.append(result)
            seen_titles.add(title)
            idx += 1

    console.print(table)
    console.print()
    
    # Play first result automatically
    if combined_results:
        result = combined_results[0]
        
        if 'url' in result:
            url = result['url']
        else:
            url = f"https://www.youtube.com/watch?v={result.get('id')}"
        
        title = result.get('title', 'Unknown')
        uploader = result.get('uploader', 'Unknown')
        duration = result.get('duration_seconds') or result.get('duration', 0)
        
        console.print(f"▶  Playing: {title}", style="bold green")
        player.play(url, title, uploader, duration)


def cli_download(player: MusicPlayer, config: ConfigManager, db: SongDatabase, song_name: str):
    """CLI download command: download first search result."""
    console.print(f"⌕  Searching...")
    results = player._search_youtube(song_name, limit=1)
    
    if not results:
        console.print(f"✘  No results found", style="bold red")
        return
    
    video = results[0]
    title = video.get("title", "Unknown")
    url = f"https://www.youtube.com/watch?v={video['id']}"

    if player.download(url, title):
        console.print(f"✓  Downloaded: {title}", style="bold green")
        local_path = player.download_dir / f"{title}.{player.audio_format}"
        db.add_song(url, title, video.get("uploader", "Unknown"), video.get("duration", 0), str(local_path))
    else:
        console.print(f"✘  Download failed", style="bold red")


def cli_queue(queue: QueueManager, player: MusicPlayer, config: ConfigManager, song_name: str):
    """CLI queue command: add first search result to queue without showing table."""
    console.print(f"⌕  Searching...")
    results_offline, results_online = player.search_simultaneous(song_name, limit=1)
    
    combined = results_offline + results_online
    
    if not combined:
        console.print(f"✘  No results found", style="bold red")
        return
    
    result = combined[0]
    
    if 'url' in result:
        url = result['url']
    else:
        url = f"https://www.youtube.com/watch?v={result.get('id')}"
    
    title = result.get('title', 'Unknown')
    uploader = result.get('uploader', 'Unknown')
    duration = result.get('duration_seconds') or result.get('duration', 0)
    
    queue.add_to_queue({"url": url, "title": title, "uploader": uploader, "duration_seconds": duration})
    console.print(f"✓  Added to queue: {title}", style="bold green")


app = typer.Typer(
    rich_markup_mode="markdown",
    add_completion=False,
    invoke_without_command=True,
    help="Music CLI with offline-first playback"
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Main entry point."""
    if not DependencyValidator.validate_all():
        sys.exit(1)

    config = ConfigManager()
    db = SongDatabase()
    playlists = PlaylistManager()
    queue = QueueManager()
    player = MusicPlayer(config, db)
    
    show_main_menu(config, player, db, playlists, queue)

 

if __name__ == "__main__":
    # Handle CLI commands before Typer processes them
    if len(sys.argv) > 1 and sys.argv[1] in ("play", "download", "queue"):
        if not DependencyValidator.validate_all():
            sys.exit(1)
        
        config = ConfigManager()
        db = SongDatabase()
        playlists = PlaylistManager()
        queue = QueueManager()
        player = MusicPlayer(config, db)
        
        command = sys.argv[1].lower()
        args = sys.argv[2:] if len(sys.argv) > 2 else []
        
        if not args:
            console.print(f"✘  Please provide a song name", style="bold red")
            sys.exit(1)
        
        song_name = " ".join(args)
        
        if command == "play":
            cli_play(player, config, db, queue, song_name)
        elif command == "download":
            cli_download(player, config, db, song_name)
        elif command == "queue":
            cli_queue(queue, player, config, song_name)
        
        sys.exit(0)
    
    # Otherwise, use normal Typer app
    app()
