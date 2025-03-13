#!/usr/bin/env python3

import os
import json
import sqlite3
import subprocess
from datetime import datetime
from typing import Optional, List
from pytube import Search
from getpass import getuser
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.prompt import Prompt

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

app = typer.Typer(rich_markup_mode="markdown", add_completion=False, invoke_without_command=True)
console = Console()

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
            console.print(f"{EMOJIS['error']} Playback error: {str(e)}", style="bold red")
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
            console.print(f"{EMOJIS['error']} Terminal playback error: {str(e)}", style="bold red")
            return False

    def download(self, url, title):
        try:
            path = f"{self.config['download_dir']}/{title}.mp3"
            result = subprocess.run(
                f"yt-dlp -f bestaudio --extract-audio --audio-format mp3 -o '{path}' '{url}'",
                shell=True,
                stdout=subprocess.DEVNULL if not self.config["show_logs"] else None,
                stderr=subprocess.DEVNULL if not self.config["show_logs"] else None
            )
            if result.returncode == 0:
                self._add_to_library(title, path)
                return True
            return False
        except Exception as e:
            console.print(f"{EMOJIS['error']} Download failed: {str(e)}", style="bold red")
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

@app.callback()
def default_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        help()

@app.command(help="🎵 Play music from YouTube or library")
def play(query: str = typer.Argument(..., help="Song title or URL")):
    player = MusicPlayer()
    
    if os.path.exists(query):
        if player.play(query, os.path.basename(query)):
            console.print(f"{EMOJIS['play']} [bold green]Now playing:[/] {os.path.basename(query)}")
        return

    with console.status("[bold green]Searching YouTube...[/]"):
        try:
            results = Search(query).results[:10]
        except Exception as e:
            console.print(f"{EMOJIS['error']} Search failed: {str(e)}", style="bold red")
            return
    os.system('cls' if os.name == 'nt' else 'clear')
    table = Table(title="🎶 Search Results", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Title", style="green")
    table.add_column("Duration", style="yellow")
    
    for idx, video in enumerate(results, 1):
        try:
            duration_seconds = video.length or 0
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            duration_str = f"{minutes}:{seconds:02d}"
        except Exception as e:
            duration_str = "N/A"
        
        table.add_row(str(idx), video.title, duration_str)
    
    console.print(table)
    
    choice = Prompt.ask("Select track (1-10)", choices=[str(i) for i in range(1,11)], default="1")
    if 1 <= int(choice) <= 10:
        video = results[int(choice)-1]
        if player.play(video.watch_url, video.title):
            console.print(f"{EMOJIS['play']} [bold green]Now playing:[/] {video.title}")

@app.command(help="💾 Download track from YouTube")
def download(query: str = typer.Argument(..., help="Search query")):
    player = MusicPlayer()
    
    with console.status("[bold green]Finding best track..."):
        video = Search(query).results[0]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    with Progress() as progress:
        task = progress.add_task("[cyan]Downloading...", total=100)
        if player.download(video.watch_url, video.title):
            progress.update(task, completed=100)
            console.print(f"{EMOJIS['tick']} [bold green]Downloaded:[/] {video.title}")

@app.command(help="📜 Show playback history")
def history():
    player = MusicPlayer()
    table = Table(title="Playback History", show_header=True, header_style="bold blue")
    table.add_column("When", style="dim", width=16)
    table.add_column("Title")
    
    for entry in player.get_history():
        table.add_row(entry['timestamp'][11:19], entry['title'])
    
    console.print(table)

@app.command(help="🗑️ Clear playback history")
def clear_history():
    player = MusicPlayer()
    player.clear_history()
    console.print(f"{EMOJIS['tick']} [bold green]History cleared[/]")

@app.command(help="📚 Show music library")
def library():
    player = MusicPlayer()
    table = Table(title="Your Library", show_header=True, header_style="bold purple")
    table.add_column("Title", style="cyan")
    table.add_column("Added", style="dim")
    
    for title, path in player.get_library():
        table.add_row(title, datetime.fromtimestamp(os.path.getctime(path)).strftime('%Y-%m-%d'))
    
    console.print(table)

@app.command(help="⚙️ Update configuration")
def config():
    player = MusicPlayer()
    console.print("Current Configuration:", style="bold yellow")
    for key, value in player.config.items():
        console.print(f"  [cyan]{key}:[/] {value}")
    
    new_config = {
        "player": Prompt.ask("Player (vlc/mpv/terminal)", default=player.config["player"]),
        "theme": Prompt.ask("Theme (dark/light/retro)", default=player.config["theme"]),
        "download_dir": Prompt.ask("Download directory", default=player.config["download_dir"])
    }
    
    player.config.update(new_config)
    player._save_config()
    console.print(f"{EMOJIS['tick']} [bold green]Configuration updated![/]")

@app.command(help="🆘 Display help information")
def help():
    """Display help information"""
    table = Table(title="Command Help", show_header=True, header_style="bold blue", 
                title_style="bold italic", width=80)
    table.add_column("Command", style="cyan", width=20)
    table.add_column("Description", style="green")
    table.add_column("Syntax", style="yellow")

    commands = [
        ("play", "🎵 Play music", "play (song/name)"),
        ("download", "💾 Download track", "download (query)"),
        ("history", "📜 Playback history", "history"),
#        ("clear-history", "🗑️ Clear history", "clear-history"),
        ("library", "📚 Music library", "library"),
        ("config", "⚙️ Configuration", "config"),
        ("help", "🆘 Display help", "help")
    ]
    
    newThing = "music_cli.py "
    
    for cmd, desc, syntax in commands:
        table.add_row(cmd, desc, newThing + syntax)  # Concatenating newThing and syntax
    
    console.print(table)
if __name__ == "__main__":
    if not os.path.exists(CONFIG_FILE):
        console.print(f"\n{EMOJIS['namaste']} [bold purple]Welcome to Music Player![/]\n")
        initial_config = {
            "player": Prompt.ask("Choose player (vlc/mpv/terminal)", default="terminal"),
            "theme": Prompt.ask("Choose theme (dark/light/retro)", default="dark"),
            "download_dir": Prompt.ask("Set download directory", default="music")
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump({**DEFAULT_CONFIG, **initial_config}, f)
        console.print(f"{EMOJIS['tick']} [bold green]Configuration saved![/]")

    app()
