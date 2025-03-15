#!/usr/bin/env python3

import os
import sys
import subprocess
import json
from datetime import datetime
from typing import List, Optional
from pytube import Search, YouTube
import typer

HISTORY_FILE = "history.json"

# Check for any invalid arguments starting with -
if any(arg.startswith('-') for arg in sys.argv[1:]):
    print("Error: Options are not supported")
    sys.exit(1)

def log_play(title: str):
    """Log played tracks with timestamp to JSON file"""
    entry = {
        "title": title,
        "timestamp": datetime.now().isoformat()
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def play_music(url: str, title: str):
    """Play audio using VLC player"""
    try:
        # Get direct audio stream URL
        stream_url = subprocess.check_output(
            ["yt-dlp", "-f", "bestaudio", "-g", url],
            text=True
        ).strip()

        # Start VLC player with the stream
        subprocess.Popen(
            ["vlc", "--play-and-exit", stream_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"🎵 Now playing: {title}")
        log_play(title)
    except Exception as e:
        print(f"Error: {str(e)}")

app = typer.Typer(add_completion=False, help=None, hidden=True)

@app.command(no_args_is_help=False, context_settings={"ignore_unknown_options": True})
def main(
    song_query: Optional[List[str]] = typer.Argument(
        None,
        help="Song name or YouTube URL (multiple words accepted)",
        show_default=False
    )
):
    # Combine multiple arguments into single query string
    query = ' '.join(song_query) if song_query else None

    # Get query from user if not provided
    if not query:
        query = typer.prompt("Enter song name or YouTube URL")

    # Handle local files
    if os.path.exists(query):
        play_music(query, os.path.basename(query))
        return

    # Handle YouTube URLs
    if "youtube.com/watch" in query:
        try:
            yt = YouTube(query)
            play_music(query, yt.title)
        except Exception as e:
            print(f"Invalid YouTube URL: {str(e)}")
        return

    # Search YouTube
    try:
        result = Search(query).results[0]
        os.system('cls' if os.name == 'nt' else 'clear')
        play_music(result.watch_url, result.title)
    except Exception as e:
        print(f"Search failed: {str(e)}")

if __name__ == "__main__":
    app()
