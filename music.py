import os
import subprocess
import json
import shutil
import sys
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from rich.console import Console
from rich.table import Table

SCRIPT_DIR = Path(__file__).resolve().parent
console = Console()

def default_music_dir() -> Path:
    if os.name == "nt":
        music = Path.home() / "Music"
    elif sys.platform == "darwin":
        music = Path.home() / "Music"
    else:
        xdg = os.environ.get("XDG_MUSIC_DIR")
        music = Path(xdg) if xdg else Path.home() / "Music"
    music.mkdir(parents=True, exist_ok=True)
    return music

class Config:
    PATH = SCRIPT_DIR / "config.json"
    DEFAULTS = {
        "audio_format":   "mp3",
        "audio_quality":  "bestaudio/best",
        "player":         "mpv",
        "search_limit":   5,
        "auto_download":  False,
        "search_timeout": 20,
    }

    def __init__(self):
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        base = {**self.DEFAULTS, "download_dir": str(default_music_dir())}
        if self.PATH.exists():
            try:
                saved = json.loads(self.PATH.read_text(encoding="utf-8"))
                base.update(saved)
            except json.JSONDecodeError:
                console.print("  ⚠  Config corrupted — using defaults\n", style="yellow")
        return base

    def save(self):
        self.PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()


# ─── Database ─────────────────────────────────────────────────────────────────

class DB:
    def __init__(self):
        self.path = SCRIPT_DIR / "music.db"
        with sqlite3.connect(self.path) as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS songs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    url         TEXT UNIQUE NOT NULL,
                    url_hash    TEXT UNIQUE NOT NULL,
                    title       TEXT NOT NULL,
                    uploader    TEXT,
                    duration    INTEGER,
                    local_path  TEXT,
                    downloaded  INTEGER DEFAULT 0,
                    played_at   TEXT,
                    last_played TEXT,
                    play_count  INTEGER DEFAULT 1
                );
            ''')

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_play(self, url, title, uploader, duration, local_path=None):
        h   = hashlib.md5(url.encode()).hexdigest()[:12]
        now = datetime.now().isoformat()
        with self._conn() as c:
            if c.execute('SELECT 1 FROM songs WHERE url_hash=?', (h,)).fetchone():
                c.execute(
                    'UPDATE songs SET last_played=?, play_count=play_count+1 WHERE url_hash=?',
                    (now, h)
                )
            else:
                c.execute(
                    '''INSERT INTO songs
                       (url, url_hash, title, uploader, duration, local_path,
                        downloaded, played_at, last_played)
                       VALUES (?,?,?,?,?,?,?,?,?)''',
                    (url, h, title, uploader, duration, local_path,
                     1 if local_path else 0, now, now)
                )

    def search_local(self, q) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                'SELECT * FROM songs WHERE LOWER(title) LIKE ? ORDER BY last_played DESC',
                (f"%{q.lower()}%",)
            ).fetchall()
        return [dict(r) for r in rows]

    def downloaded(self) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                'SELECT * FROM songs WHERE downloaded=1 AND local_path IS NOT NULL ORDER BY last_played DESC'
            ).fetchall()
        return [dict(r) for r in rows if Path(r['local_path']).exists()]

    def history(self, limit=20) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                'SELECT * FROM songs ORDER BY last_played DESC LIMIT ?', (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def by_url(self, url) -> Optional[Dict]:
        with self._conn() as c:
            r = c.execute('SELECT * FROM songs WHERE url=?', (url,)).fetchone()
        return dict(r) if r else None


# ─── Player ───────────────────────────────────────────────────────────────────

class Player:
    def __init__(self, config: Config, db: DB):
        self.cfg = config
        self.db  = db
        self.download_dir = Path(config.get("download_dir"))
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def yt_search(self, query, limit=5) -> List[Dict]:
        cmd     = ["yt-dlp", f"ytsearch{limit}:{query}", "--flat-playlist", "-J", "--no-warnings"]
        timeout = self.cfg.get("search_timeout")
        for extra in [[], ["--no-check-certificates"]]:
            try:
                proc = subprocess.run(
                    cmd + extra, capture_output=True, text=True, timeout=timeout
                )
                raw = proc.stdout.strip()
                if not raw:
                    continue
                entries = [e for e in json.loads(raw).get("entries", []) if e]
                if entries:
                    return entries
            except Exception:
                continue
        return []

    def search(self, query) -> Tuple[List[Dict], List[Dict]]:
        return self.db.search_local(query), self.yt_search(query, self.cfg.get("search_limit"))

    def _local(self, url) -> Optional[str]:
        e = self.db.by_url(url)
        if e and e.get("local_path") and Path(e["local_path"]).exists():
            return e["local_path"]
        return None

    def _stream_url(self, url) -> Optional[str]:
        try:
            return subprocess.check_output(
                ["yt-dlp", "-f", self.cfg.get("audio_quality"), "-g", url],
                stderr=subprocess.DEVNULL, text=True, timeout=15
            ).strip()
        except Exception:
            return None

    def download(self, url, title) -> Optional[str]:
        safe = "".join(c for c in title if c.isalnum() or c in " -_").rstrip()
        fmt  = self.cfg.get("audio_format")
        out  = self.download_dir / f"{safe}.{fmt}"
        if out.exists():
            return str(out)
        console.print(f"\n  ⬇  downloading: {safe}", style="dim")
        try:
            r = subprocess.run(
                ["yt-dlp", "-f", self.cfg.get("audio_quality"), "--extract-audio",
                 "--audio-format", fmt, "-o", str(out), url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300
            )
            return str(out) if r.returncode == 0 and out.exists() else None
        except Exception:
            return None

    def play(self, url, title, uploader="", duration=0) -> bool:
        local = self._local(url)
        if not local and self.cfg.get("auto_download"):
            local = self.download(url, title)

        is_local = bool(local and not local.startswith("http"))
        tag = "⊘ offline" if is_local else "◈ streaming"
        console.print(f"\n  ▶  {title}  [dim]{tag}[/dim]\n")

        self.db.record_play(url, title, uploader, duration, local if is_local else None)

        if is_local:
            return self._mpv(local, stream=False)

        # Try stream URL first, fall back to passing YouTube URL directly to mpv
        stream = self._stream_url(url)
        if stream:
            ok = self._mpv(stream, stream=True)
            if ok:
                return True
            console.print("  [dim]stream failed — retrying via direct URL...[/dim]\n")

        return self._mpv(url, stream=True)

    def _mpv(self, path, stream=False) -> bool:
        args = [self.cfg.get("player"), "--log-file=/dev/null", "--no-config"]
        if not stream:
            args.append("--no-cache")
        args.append(path)
        try:
            subprocess.run(args, timeout=None)
            return True
        except FileNotFoundError:
            console.print("  ✘  mpv not found — install from https://mpv.io\n", style="red")
            return False
        except Exception as e:
            console.print(f"  ✘  {e}\n", style="red")
            return False


# ─── Dependency check ─────────────────────────────────────────────────────────

def check_deps():
    missing = [c for c in ("yt-dlp", "mpv") if not shutil.which(c)]
    if missing:
        console.print(f"\n  ✘  Missing: {', '.join(missing)}\n", style="bold red")
        console.print("     mpv    → https://mpv.io", style="dim")
        console.print("     yt-dlp → pip install yt-dlp\n", style="dim")
        sys.exit(1)


# ─── UI helpers ───────────────────────────────────────────────────────────────

def clr():
    os.system("cls" if os.name == "nt" else "clear")

def fmt(s):
    s = int(s) if s else 0
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

def song_url(r) -> Optional[str]:
    if r.get("url"):
        return r["url"]
    vid = r.get("id") or r.get("video_id")
    return f"https://www.youtube.com/watch?v={vid}" if vid else None

def merge_results(offline, online) -> List[Dict]:
    combined, seen = [], set()
    for r in offline:
        t = r.get("title", "")
        if t not in seen:
            r["_source"] = "offline"; combined.append(r); seen.add(t)
    for r in online:
        t = r.get("title", "")
        if t not in seen:
            r["_source"] = "online";  combined.append(r); seen.add(t)
    return combined

def print_results(combined: List[Dict]):
    t = Table(show_header=True, header_style="bold white", box=None, padding=(0, 2))
    t.add_column("#",        style="cyan",    width=3,  no_wrap=True)
    t.add_column("Title",    style="white",   overflow="ellipsis", max_width=58)
    t.add_column("Artist",   style="dim",     max_width=22)
    t.add_column("Duration", style="dim",     width=8, justify="right")
    t.add_column("",         style="dim",     width=2)
    for i, r in enumerate(combined, 1):
        src = "⊘" if r.get("_source") == "offline" else "◈"
        dur = r.get("duration_seconds") or r.get("duration", 0)
        t.add_row(str(i), r.get("title", "?"), r.get("uploader", ""), fmt(dur), src)
    console.print()
    console.print(t)
    console.print()

def prompt(hint=""):
    if hint:
        console.print(f"  [dim]{hint}[/dim]")
    return input("  ❯ ").strip()


# ─── Screens ──────────────────────────────────────────────────────────────────

def do_search(query: str, player: Player, db: DB) -> Optional[Dict]:
    """Run a search, print table, let user pick. Returns chosen result or None."""
    console.print("  searching...", style="dim", end="\r")
    offline, online = player.search(query)
    combined = merge_results(offline, online)

    if not combined:
        console.print("  ✘  No results — check your connection or try a different query\n", style="red")
        input("  Enter to continue...")
        return None

    clr()
    print_results(combined)
    raw = prompt("number → play   d+number → download   0 → back").lower()

    if not raw or raw == "0":
        return None

    action   = "download" if raw.startswith("d") else "play"
    num_str  = raw[1:].strip() if raw.startswith("d") else raw

    try:
        idx = int(num_str) - 1
        r   = combined[idx]
    except (ValueError, IndexError):
        console.print("  ✘  Invalid\n", style="red")
        input("  Enter...")
        return None

    url    = song_url(r)
    title  = r.get("title", "?")
    artist = r.get("uploader", "")
    dur    = r.get("duration_seconds") or r.get("duration", 0)

    if not url:
        console.print("  ✘  Could not resolve URL\n", style="red")
        input("  Enter...")
        return None

    if action == "play":
        player.play(url, title, artist, dur)
    elif action == "download":
        local = player.download(url, title)
        if local:
            db.record_play(url, title, artist, dur, local)
            console.print(f"  ✓  Saved to {local}\n", style="green")
        else:
            console.print("  ✘  Download failed\n", style="red")
        input("  Enter...")

    return r


def library_screen(player: Player, db: DB):
    while True:
        clr()
        songs = db.downloaded()
        console.print(f"\n  [bold]Library[/]  [dim]— {len(songs)} downloaded songs[/]\n")

        if not songs:
            console.print("  No downloaded songs yet.\n", style="dim")
            input("  Enter to go back...")
            return

        t = Table(show_header=True, header_style="bold white", box=None, padding=(0, 2))
        t.add_column("#",      style="cyan",  width=3)
        t.add_column("Title",  style="white", overflow="ellipsis", max_width=58)
        t.add_column("Artist", style="dim",   max_width=22)
        for i, s in enumerate(songs, 1):
            t.add_row(str(i), s.get("title", "?"), s.get("uploader", ""))
        console.print(t)
        console.print()

        raw = prompt("number → play   0 → back").lower()
        if not raw or raw == "0":
            return
        try:
            s   = songs[int(raw) - 1]
            url = s.get("url") or s.get("local_path")
            player.play(url, s["title"], s.get("uploader", ""), s.get("duration", 0))
        except (ValueError, IndexError):
            pass


def history_screen(player: Player, db: DB):
    clr()
    songs = db.history(20)

    if not songs:
        console.print("\n  No history yet.\n", style="dim")
        input("  Enter to go back...")
        return

    console.print(f"\n  [bold]History[/]  [dim]— last {len(songs)} played[/]\n")

    t = Table(show_header=True, header_style="bold white", box=None, padding=(0, 2))
    t.add_column("#",      style="cyan",  width=3)
    t.add_column("Title",  style="white", overflow="ellipsis", max_width=52)
    t.add_column("Artist", style="dim",   max_width=22)
    t.add_column("Played", style="dim",   width=14)

    for i, s in enumerate(songs, 1):
        try:
            date = datetime.fromisoformat(s.get("played_at", "")).strftime("%b %d  %H:%M")
        except Exception:
            date = "—"
        t.add_row(str(i), s.get("title", "?"), s.get("uploader", ""), date)

    console.print(t)
    console.print()

    raw = prompt("number → play   0 → back").lower()
    if not raw or raw == "0":
        return
    try:
        s   = songs[int(raw) - 1]
        player.play(s["url"], s["title"], s.get("uploader", ""), s.get("duration", 0))
    except (ValueError, IndexError):
        pass


def settings_screen(config: Config, player: Player):
    keys = ["download_dir", "audio_format", "audio_quality", "search_limit", "auto_download"]
    while True:
        clr()
        console.print("\n  [bold]Settings[/]\n")
        for i, k in enumerate(keys, 1):
            console.print(f"  [cyan]{i}[/]  {k:<20}  [dim]{config.get(k)}[/dim]")
        console.print()
        raw = prompt("number → edit   0 → back")
        if raw == "0":
            return
        try:
            k = keys[int(raw) - 1]
            v = input(f"\n  {k} = ").strip()
            if not v:
                continue
            if k == "search_limit":    v = int(v)
            elif k == "auto_download": v = v.lower() in ("1", "true", "yes")
            elif k == "download_dir":
                Path(v).mkdir(parents=True, exist_ok=True)
                player.download_dir = Path(v)
            config.set(k, v)
            console.print("  ✓  Saved\n", style="green")
        except (ValueError, IndexError):
            pass


# ─── Main interactive loop ────────────────────────────────────────────────────

def interactive(config: Config, db: DB, player: Player):
    while True:
        clr()
        console.print("\n  [bold cyan]music[/]\n")
        console.print("  Enter a song title to search.\n")
        console.print("  [dim]l → library   h → history   , → settings   0 → exit[/dim]\n")

        raw = input("  ❯ ").strip()

        if not raw:
            continue
        elif raw == "0":
            console.print("\n  bye\n", style="dim")
            break
        elif raw == "l":
            library_screen(player, db)
        elif raw == "h":
            history_screen(player, db)
        elif raw == ",":
            settings_screen(config, player)
        else:
            clr()
            do_search(raw, player, db)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_deps()
    config = Config()
    db     = DB()
    player = Player(config, db)

    args = sys.argv[1:]

    # Direct play: python music.py "song name"
    if args and not args[0].startswith("--"):
        query = " ".join(args)
        console.print(f"\n  ⌕  {query}\n", style="dim")
        results = player.yt_search(query, limit=config.get("search_limit"))
        if not results:
            console.print("  ✘  No results — check your connection or try a different query\n", style="red")
            sys.exit(1)
        combined = merge_results([], results)
        r   = combined[0]
        url = song_url(r)
        if not url:
            console.print("  ✘  Could not resolve URL\n", style="red")
            sys.exit(1)
        player.play(url, r.get("title", ""), r.get("uploader", ""), r.get("duration", 0))
        sys.exit(0)

    interactive(config, db, player)


if __name__ == "__main__":
    main()
