#!/usr/bin/env python3

import os
import subprocess
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
# from rich import box

EMOJIS = {
    "play": "▶️",
    "error": "❌",
    "pause": "⏸️",
    "stop": "⏹️",
    "neutral": "● "
}

app = typer.Typer(
    rich_markup_mode="markdown", add_completion=False, invoke_without_command=True
)

console = Console()


class MusicPlayer:
    def save_history(self, title, uploader, url):
        history_path = "history.json"
        from datetime import datetime

        entry = {
            "title": title,
            "uploader": uploader,
            "played": datetime.now().strftime("%Y/%m/%d"),
            "url": url
        }

        # Load existing history
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        data.append(entry)

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def __init__(self):
        self.player = "mpv"
        self.download_dir = "music"
        self._init_data_dir()

    def _init_data_dir(self):
        os.makedirs(self.download_dir, exist_ok=True)

    def play(self, url, title):
        try:
            # Extract the stream URL for the YouTube video
            stream_url = subprocess.check_output(
                ["yt-dlp", "-f", "bestaudio", "-g", url],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            # Save history
            uploader = "Unknown"  # Default uploader
            self.save_history(title, uploader, url)

            console.print(f"{EMOJIS['play']} [bold green]Now playing:[/] {title}")
            # Run mpv to play the stream
            subprocess.run(['mpv', '--no-cache', '--log-file=/dev/null', '--no-config', '--fs', stream_url])

            return True

        except Exception as e:
            # Handle playback error
            console.print(f"{EMOJIS['error']} Playback error: {str(e)}", style="bold red")
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
            return True

        except Exception as e:
            console.print(
                f"{EMOJIS['error']} Download failed: {str(e)}", style="bold red"
            )
            return False

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


@app.command(help="Play music from YouTube")
def play(query: str = typer.Argument(..., help="Song title or URL")):
    player = MusicPlayer()

    if os.path.exists(query):
        return

    with console.status("[bold green]Searching For The Song...[/]"):
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

    table.add_column("Index", style="cyan", justify="center", max_width=5)
    table.add_column("Title", style="green", overflow="ellipsis", max_width=80)
    table.add_column("Duration", style="yellow", justify="center", max_width=10)

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
            console.print(f"{EMOJIS['neutral']}[bold green]Last played:[/] {title}\n")


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
        ("help", "Display help", "help"),
    ]

    newThing = "music_cli.py "

    for cmd, desc, syntax in commands:
        table.add_row(cmd, desc, newThing + syntax)

    console.print(table)


if __name__ == "__main__":
    app()

