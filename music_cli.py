import os
import sys
import cmd
import json
import time
import sqlite3
import subprocess
from datetime import datetime
from pytube import Search
from getpass import getuser
from threading import Thread

# Configuration
CONFIG_FILE = "music_config.json"
DEFAULT_CONFIG = {
    "player": "terminal",
    "theme": "dark",
    "download_dir": "music",
    "history_file": "history.json",
    "library_db": "library.db",
    "show_logs": False
}

EMOJIS = {
    "namaste": "🙏",
    "bye": "👋",
    "tick": "✅",
    "music": "🎵",
    "error": "❌",
    "play": "▶️",
    "pause": "⏸️",
    "stop": "⏹️"
}

THEMES = {
    "dark": {"prompt": "🔮", "text": "\033[37m"},
    "light": {"prompt": "☀️", "text": "\033[30m"},
    "retro": {"prompt": "📼", "text": "\033[33m"}
}

class MusicPlayer:
    def __init__(self):
        self.config = self._load_config()
        self.current_process = None
        self.paused = False
        self._init_data_dir()
        self._init_library()

    def _init_data_dir(self):
        os.makedirs(self.config["download_dir"], exist_ok=True)
        if not os.path.exists(self.config["history_file"]):
            open(self.config["history_file"], "w").close()

    def _init_library(self):
        with sqlite3.connect(self.config["library_db"]) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY,
                    title TEXT UNIQUE,
                    path TEXT,
                    added_date DATETIME
                )
            """)

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f)

    def _log_history(self, title):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "play",
            "title": title
        }
        with open(self.config["history_file"], "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _run_command(self, cmd):
        return subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL if not self.config["show_logs"] else None,
            stderr=subprocess.DEVNULL if not self.config["show_logs"] else None,
            shell=True
        )

    def play(self, url, title):
        try:
            if self.config["player"] == "terminal":
                return self._play_in_terminal(url, title)
            
            stream_url = subprocess.check_output(
                ["yt-dlp", "-f", "bestaudio", "-g", url],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            
            self.current_process = subprocess.Popen(
                [self.config["player"], stream_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._log_history(title)
            return True
        except Exception as e:
            print(f"{EMOJIS['error']} Playback error: {str(e)}")
            return False

    def _play_in_terminal(self, url, title):
        try:
            self.current_process = subprocess.Popen(
                ["mpv", "--no-video", url],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._log_history(title)
            return True
        except Exception as e:
            print(f"{EMOJIS['error']} Terminal playback error: {str(e)}")
            return False

    def terminal_control(self, action):
        if self.current_process and self.current_process.poll() is None:
            if action == "pause":
                self.current_process.stdin.write(b"cycle pause\n")
                self.current_process.stdin.flush()
                self.paused = not self.paused
            elif action == "stop":
                self.current_process.terminate()
            return True
        return False

    def download(self, url, title):
        try:
            path = f"{self.config['download_dir']}/{title}.mp3"
            result = self._run_command(
                f"yt-dlp -f bestaudio --extract-audio --audio-format mp3 -o '{path}' '{url}'"
            )
            if result.returncode == 0:
                self._add_to_library(title, path)
                return True
            return False
        except Exception as e:
            print(f"{EMOJIS['error']} Download failed: {str(e)}")
            return False

    def _add_to_library(self, title, path):
        with sqlite3.connect(self.config["library_db"]) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO songs (title, path, added_date)
                VALUES (?, ?, datetime('now'))
            """, (title, path))

    def get_history(self):
        try:
            with open(self.config["history_file"], "r") as f:
                return [json.loads(line) for line in f.readlines()]
        except FileNotFoundError:
            return []

    def clear_history(self):
        open(self.config["history_file"], "w").close()

    def search_library(self, query):
        with sqlite3.connect(self.config["library_db"]) as conn:
            cursor = conn.execute("""
                SELECT title, path FROM songs
                WHERE title LIKE ?
            """, (f"%{query}%",))
            return cursor.fetchall()

    def get_library(self):
        with sqlite3.connect(self.config["library_db"]) as conn:
            cursor = conn.execute("SELECT title, path FROM songs")
            return cursor.fetchall()

class MusicCLI(cmd.Cmd):
    def __init__(self):
        super().__init__()
        self.player = MusicPlayer()
        self._setup_initial_config()
        self.theme = THEMES[self.player.config["theme"]]
        self.prompt = f"{self.theme['prompt']} {self.theme['text']}> \033[0m"
        self._show_welcome()

    def _setup_initial_config(self):
        if not os.path.exists(CONFIG_FILE):
            print(f"\n{EMOJIS['namaste']} Welcome to Terminal Music Player!")
            self.player.config["player"] = input(
                "Choose player (vlc/mpv/terminal) [terminal]: "
            ).lower() or "terminal"
            
            self.player.config["theme"] = input(
                "Choose theme (dark/light/retro) [dark]: "
            ).lower() or "dark"
            
            self.player.config["download_dir"] = input(
                f"Download directory [music]: "
            ) or "music"
            
            self.player.config["show_logs"] = input(
                "Show detailed logs? (y/n) [n]: "
            ).lower() == "y"
            
            self.player._save_config()

    def _show_welcome(self):
        username = getuser()
        print(f"\n{self.theme['text']}{EMOJIS['namaste']} Hello {username}!\033[0m")
        print(f"{self.theme['text']}{'-'*40}\033[0m")
        print(HELP_TEXT)

    def _print_header(self, text):
        print(f"\n{self.theme['text']}🎶 {text} \033[0m")

    def do_play(self, arg):
        """Play music from YouTube or library"""
        if not arg:
            self._print_header("Library Songs:")
            songs = self.player.get_library()
            for idx, (title, path) in enumerate(songs, 1):
                print(f"{idx}. {title}")
            choice = input("Select number or enter search query: ")
            if choice.isdigit():
                song = songs[int(choice)-1]
                self._play_song(song[1], song[0])
                return
            arg = choice

        if os.path.exists(arg):
            self._play_song(arg, os.path.basename(arg))
            return

        results = Search(arg).results[:5]
        self._print_header("Search Results:")
        for i, video in enumerate(results, 1):
            print(f"{i}. {video.title}")
            
        choice = input("Select number (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= 5:
            video = results[int(choice)-1]
            if self.player.play(video.watch_url, video.title):
                print(f"{EMOJIS['play']} Now playing: {video.title}")

    def _play_song(self, path, title):
        if self.player.config["player"] == "terminal":
            Thread(target=self._terminal_playback_controls).start()
        if self.player.play(path, title):
            print(f"{EMOJIS['play']} Now playing: {title}")

    def _terminal_playback_controls(self):
        while True:
            cmd = input(f"{EMOJIS['pause']} Press [p]ause/[s]top: ").lower()
            if cmd == "p":
                self.player.terminal_control("pause")
            elif cmd == "s":
                self.player.terminal_control("stop")
                break
            time.sleep(0.1)

    def do_download(self, arg):
        """Download track from YouTube"""
        if not arg:
            print(f"{EMOJIS['error']} Please provide a search query")
            return
            
        video = Search(arg).results[0]
        if self.player.download(video.watch_url, video.title):
            print(f"{EMOJIS['tick']} Downloaded: {video.title}")

    def do_history(self, arg):
        """Show playback history"""
        self._print_header("Playback History:")
        for entry in self.player.get_history():
            print(f"[{entry['timestamp'][:19]}] {entry['title']}")

    def do_clear_history(self, arg):
        """Clear playback history"""
        self.player.clear_history()
        print(f"{EMOJIS['tick']} History cleared")

    def do_library(self, arg):
        """Show downloaded songs"""
        self._print_header("Music Library:")
        for title, path in self.player.get_library():
            print(title)

    def do_search(self, arg):
        """Search local library"""
        self._print_header("Search Results:")
        results = self.player.search_library(arg)
        for title, path in results:
            print(title)

    def do_config(self, arg):
        """Update configuration settings"""
        print("\nCurrent Configuration:")
        for key, value in self.player.config.items():
            print(f"{key}: {value}")
            
        new_player = input("\nNew player (vlc/mpv/terminal): ") or None
        if new_player:
            self.player.config["player"] = new_player
            
        new_theme = input("New theme (dark/light/retro): ") or None
        if new_theme:
            self.player.config["theme"] = new_theme
            self.theme = THEMES[new_theme]
            self.prompt = f"{self.theme['prompt']} {self.theme['text']}> \033[0m"
            
        self.player._save_config()
        print(f"{EMOJIS['tick']} Configuration updated")

    def do_help(self, arg):
        """Show help"""
        print(HELP_TEXT)

    def do_exit(self, arg):
        """Exit the program"""
        print(f"\n{EMOJIS['bye']} Goodbye!\n")
        sys.exit()

HELP_TEXT = f"""
{EMOJIS['music']} Available Commands:

play [query]      - Play music from YouTube or library
download [query]  - Download track from YouTube
history           - Show playback history
clear-history     - Reset history
library           - Show downloaded songs
search [query]    - Search local library
config            - Update settings
help              - Show this help
exit              - Quit program
"""

if __name__ == "__main__":
    MusicCLI().cmdloop()
