# Music-CLI 🎵

Welcome to **Music-CLI**, a terminal-based music player that lets you **play and download any YouTube video within the terminal** or **play those songs seamlessly using VLC or MPV**. This lightweight, customizable music player is designed for CLI lovers who want full control over their music experience.

---

## Features ✨

- **Play Music**: Stream or play music directly from YouTube or your local library.
- **Download Tracks**: Download your favorite songs as MP3 files effortlessly.
- **Library Management**: Organize and search your downloaded music.
- **Playback History**: Keep track of your listening history.
- **Customizable Themes**: Choose from dark, light, or retro themes.
- **Terminal Controls**: Pause, stop, and control playback directly from the terminal.
- **Multiple Players**: Supports `mpv`, `vlc`, or terminal-based playback.

---

## Installation 🛠️

### Prerequisites
Before using Music-CLI, ensure you have the following installed:
- **Python 3.8+**
- **yt-dlp** (for downloading and streaming music)
- **mpv** or **vlc** (for playback)

You can install the dependencies using the following commands:

```bash
# Install yt-dlp
pip install yt-dlp

# Install mpv (Recommended)
sudo apt install mpv  # For Debian/Ubuntu
brew install mpv      # For macOS
sudo pacman -S mpv    # For Arch based Linux Distros
```

### Clone the Repository
Clone this repository to your local machine:

```bash
git clone https://github.com/your-username/music-cli.git
cd music-cli
```

### Add to `/usr/bin` (Optional)
To make the script accessible system-wide, you can add it to `/usr/bin`:

```bash
sudo ln -s $(pwd)/main.py /usr/bin/music-cli
```

Now you can run the player from anywhere using the `music-cli` command.

---

## Usage 🎶

Run the script using Python:

```bash
python main.py
```

### Commands
Here are the available commands you can use in the interactive CLI:

| Command           | Description                                      |
|-------------------|--------------------------------------------------|
| `play [query]`    | Play music from YouTube or your local library.   |
| `download [query]`| Download a track from YouTube.                   |
| `history`         | View your playback history.                      |
| `clear-history`   | Clear your playback history.                     |
| `library`         | List all downloaded songs in your library.       |
| `search [query]`  | Search your local library for a song.            |
| `config`          | Update player, theme, or other settings.         |
| `help`            | Show the help menu.                              |
| `exit`            | Exit the program.                                |

### Example Workflow
1. **Play a Song**:
   ```bash
   play "Bohemian Rhapsody"
   ```
2. **Download a Song**:
   ```bash
   download "Shape of You"
   ```
3. **Search Your Library**:
   ```bash
   search "Queen"
   ```

---

## Contributing 🤝

We welcome contributions! Here's how you can get started:

1. **Fork the Repository**: Create your own fork of the project.
2. **Install Requirements**: Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. **Make Changes**: Implement your changes or add new features.
4. **Test Your Code**: Ensure your changes work as expected.
5. **Submit a Pull Request**: Open a PR with a detailed description of your changes.

### Development Setup
To set up the project for development:
```bash
git clone https://github.com/your-username/music-cli.git
cd music-cli
```
### (Optional)
```
python -m venv venv
source venv/bin/activate
```
```
pip install -r requirements.txt
```

---

## Configuration ⚙️

The player is highly customizable. You can configure the following settings:
- **Player**: Choose between `mpv`, `vlc`, or `terminal` playback.
- **Theme**: Select from `dark`, `light`, or `retro` themes.
- **Download Directory**: Set the folder where downloaded songs are saved.
- **Show Logs**: Enable or disable detailed logs.

To update the configuration, use the `config` command in the CLI.

---

## License 📜

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## Support 💬

If you encounter any issues or have suggestions, feel free to open an issue on GitHub. Your feedback is greatly appreciated!

---

Enjoy your music! 🎶
