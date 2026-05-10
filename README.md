# MusicTui
A terminal music player written in Python. Plays local files through mpv, controlled entirely from the keyboard.

## Screenshots

![Main Player](pictures/main-player.png)

*The main interface showing playlist and now playing*

![Search Feature](pictures/search.png)

*Searching for "undead"*

![Help Screen](pictures/help-screen.png)

*Press 'h' for keyboard shortcuts*

## Features
- Plays MP3, FLAC, OGG, WAV, AAC, M4A, Opus, WMA, APE and more
- Search your library instantly
- Shuffle and repeat modes
- Volume control and mute
- Skip forward/backward by 5s or 10s
- Press 0–9 to jump to any 10% point in a song (like YouTube)
- Customizable accent color via config file
- Press h for a full keybinds screen

## Platform Support
|Platform          |Supported| 
|------------------|---------|
|Linux             |✅Full support|
|macOS             |✅Full support|
|WSL2 (Windows)    |✅Works|
|Native Windows    |❌Not supported|

Native Windows is not supported because this player communicates with mpv over Unix sockets, which Windows does not have. mpv itself runs on Windows fine, but the IPC layer this player uses does not.

## Dependencies
- Python 3.8+
- mpv
- ffmpeg (for audio duration detection)

## Installation
### 1. Install Dependencies
- Arch Linux
  
  ```bash
  sudo pacman -S python python-pip mpv ffmpeg
  ```
- Ubuntu/Debian
  
  ```bash
  sudo apt install python3 python3-pip mpv ffmpeg
  ```
- macOS
  
  ```bash
  brew install python mpv ffmpeg
  ```
- Windows (WSL2)
  
  ```bash
  sudo apt install python3 python3-pip mpv ffmpeg
  ```
  
### 2. Get the player
Clone the repo:
```bash
git clone https://github.com/BaconPancakes7959/musictui.git
cd musictui
```
Or download just the script:
```bash
curl -O https://raw.githubusercontent.com/BaconPancakes7959/musictui/main/music_player.py
```

### 3. Create virtual environment (recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate
```
  
### 4. Install Python dependencies
With the virtualenv active:
```bash
pip install mutagen wcwidth
```

### 5. Run the App
With dependencies installed and your virtualenv active:
```bash
python musictui.py
```
By default the player looks for music in ~/Music. See Configuration below to change this.

## Configuration
On first run, a config file is created at:
`~/.config/musictui/config.ini`
Open it in any text editor:
```ini
[theme]
accent_color = 215

[player]
music_dir = ~/Music
```
`accent_color` is a number from 0–255 (xterm-256 color palette). Restart the player after changing it.
To browse colors, run:
```bash
python3 -c "
import curses
def show(s):
    curses.start_color()
    curses.use_default_colors()
    for i in range(1, 256):
        curses.init_pair(i, i, -1)
        s.addstr(i // 16, (i % 16) * 5, f'{i:3}', curses.color_pair(i))
    s.getch()
curses.wrapper(show)
"
```
`music_dir` sets where the player looks for music. Supports ~ for your home directory. The player searches recursively, so subdirectories are included.

## Keybinds
| Key | Action |
|-----|--------|
| `Enter` | Play selected song |
| `Space` | Pause / Resume |
| `p / n` |Previous / Next song|
| `← / →` |Seek −5 / +5 seconds|
| `j / l` |Seek −10 / +10 seconds|
| `0–9`   |Jump to 0%–90% of song|
| `- / =` |Volume down / up|
| `m`     |Toggle mute|
| `↑ / ↓` |Navigate list|
| `/`     |Search|
| `Esc / c` |Clear search|
| `s`     |Toggle shuffle|
| `r`     |Toggle repeat|
| `h`     |Keybinds screen|
| `q`     |Quit|

## Troubleshooting
No songs found — check that `music_dir` in your config points to the right folder and that it contains `.mp3` or other supported files in it or any subfolder.

`wcwidth` or `mutagen` import error — make sure you installed into the same Python you're running the script with. If using a venv, confirm it's activated: `which python3` should point inside your `.venv` folder.

Colors look wrong — your terminal may not support 256 colors. Run `echo $TERM —` it should say `xterm-256color` or similar. Most modern terminals support this by default.

Player exits but mpv keeps playing — this shouldn't happen with the current version, but if it does: `pkill mpv`.

macOS: `curses` errors — make sure you're using a proper terminal emulator (iTerm2, Alacritty, Ghostty). The default macOS Terminal.app can have issues with some curses features.
  
