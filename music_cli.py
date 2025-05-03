#!/usr/bin/env python3

import os
import sqlite3
import subprocess
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich import box

EMOJIS = {
    "play": "▶️",
    "error": "❌",
    "pause": "⏸️",
    "stop": "⏹️",
}

app = typer.Typer(
    rich_markup_mode="markdown", add_completion=False, invoke_without_command=True
)

console = Console()

class MusicPlayer:
    def __init__(self):
        self.player = "mpv"
        self.download_dir = "music"
        self._init_data_dir()
        self._init_library()

    def _init_data_dir(self):
        os.makedirs(self.download_dir, exist_ok=True)

    def _init_library(self):
        with sqlite3.connect("library.db") as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY,
                    title TEXT UNIQUE,
                    path TEXT,
                    added_date DATETIME
                )
                """
            )

    def play(self, url, title):
        try:
            stream_url = subprocess.check_output(
                ["yt-dlp", "-f", "bestaudio", "-g", url],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()

            console.print(
                f"{EMOJIS['play']} [bold green]Now playing:[/] {title}"
            )
            subprocess.run(['mpv', '--no-cache', stream_url])

            return True

        except Exception as e:
            console.print(
                f"{EMOJIS['error']} Playback error: {str(e)}", style="bold red"
            )
            return False

    def download(self, url, title):
        try:
            path = f"{self.download_dir}/{title}.mp3"
            result = subprocess.run(
                f"yt-dlp -f bestaudio --extract-audio --audio-format mp3 -o '{path}' '{url}'",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if result.returncode == 0:
                self._add_to_library(title, path)
                return True

            return False

        except Exception as e:
            console.print(
                f"{EMOJIS['error']} Download failed: {str(e)}", style="bold red"
            )
            return False

    def _add_to_library(self, title, path):
        with sqlite3.connect("library.db") as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO songs (title, path, added_date)
                VALUES (?, ?, datetime('now'))
                """,
                (title, path),
            )

    def get_library(self):
        with sqlite3.connect("library.db") as conn:
            cursor = conn.execute("SELECT title, path FROM songs")
            return cursor.fetchall()

    def search_youtube(self, query, limit=10):
        try:
            result = subprocess.check_output(
                [
                    "yt-dlp",
                    f"ytsearch{limit}:{query}",
                    "--flat-playlist",
                    "-J"
                ],
                text=True
            )
            data = json.loads(result)
            return data.get("entries", [])
        except Exception as e:
            console.print(f"{EMOJIS['error']} Search error: {str(e)}", style="bold red")
            return []


@app.command(help="Play music from YouTube or library")
def play(query: str = typer.Argument(..., help="Song title or URL")):
    player = MusicPlayer()

    if os.path.exists(query):
        return

    with console.status("[bold green]Searching YouTube...[/]"):
        results = player.search_youtube(query, limit=10)
        if not results:
            return

    os.system("cls" if os.name == "nt" else "clear")

    table = Table(
        title="Search Results",
        show_header=True,
        header_style="bold magenta",
        # box=box.SIMPLE_HEAVY   # cleaner and sturdier
    )

    table.add_column("#", style="cyan", justify="right", width=3)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=80)
    table.add_column("Duration", style="yellow", justify="center", width=10)

    def format_time(seconds):
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

    for idx, video in enumerate(results, 1):
        duration_str = format_time(video['duration'])
        title = video.get("title", "Unknown Title")
        table.add_row(str(idx), title, duration_str)

    console.print(table)

    choice = typer.prompt("Select track (1-10)", default="1", type=int)

    if 1 <= choice <= 10:
        video = results[choice - 1]
        title = video.get("title", "Unknown Title")
        url = f"https://www.youtube.com/watch?v={video['id']}"

        if player.play(url, title):
            console.print(f"{EMOJIS['play']} [bold green]Now playing:[/] {title}")


@app.command(help="Download track from YouTube")
def download(query: str = typer.Argument(..., help="Search query")):
    player = MusicPlayer()

    with console.status("[bold green]Finding best track..."):
        results = player.search_youtube(query, limit=1)
        if not results:
            return
        video = results[0]
        title = video.get("title", "Unknown Title")
        url = f"https://www.youtube.com/watch?v={video['id']}"

    os.system("cls" if os.name == "nt" else "clear")

    with Progress() as progress:
        task = progress.add_task("[cyan]Downloading...", total=100)
        if player.download(url, title):
            progress.update(task, completed=100)
            console.print(f"{EMOJIS['play']} [bold green]Downloaded:[/] {title}")


@app.command(help="Show music library")
def library():
    player = MusicPlayer()

    table = Table(title="Your Library", show_header=True, header_style="bold purple")
    table.add_column("Title", style="cyan")

    for title, path in player.get_library():
        table.add_row(title)

    console.print(table)


@app.command(help="Display help information")
def help():
    """Display help information"""
    table = Table(
        title="Command Help",
        show_header=True,
        header_style="bold blue",
        title_style="bold italic",
        width=80,
    )
    table.add_column("Command", style="cyan", width=20)
    table.add_column("Description", style="green")
    table.add_column("Syntax", style="yellow")

    commands = [
        ("play", "Play music", "play (song/name)"),
        ("download", "Download track", "download (query)"),
        ("library", "Music library", "library"),
        ("help", "Display help", "help"),
    ]

    newThing = "music_cli.py "

    for cmd, desc, syntax in commands:
        table.add_row(cmd, desc, newThing + syntax)

    console.print(table)


if __name__ == "__main__":
    console.print(f"\n{EMOJIS['play']} [bold green]Welcome to Music Player![/]\n")
    app()


