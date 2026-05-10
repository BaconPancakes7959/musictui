# MusicTui
A TUI music player written in Python that plays music directly from your local files. 

## Features
- Play media formats
  
  - MP3, FLAC, OGG, WAV, AAC, M4A, Opus, WMA, APE
  - Extra: AC3, DTS, TrueHD, AMR, AIFF
    
- Search your library
- Customizable color theme
- Skip forward/backward 5 and 10 seconds
- Volume control
- Shuffle mode
- Repeat mode
- Press 0-9 to jump to 0%-90% of the current song
- Press h for a Keybinds menu

## Dependencies
- Python 3.8+
- mpv

## Installation
### Install Dependencies
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
  
### Install MusicTui
Download The Code:
  ```bash
  git clone https://github.com/BaconPancakes7959/musictui.git
  cd musictui
  ```
Or just copy paste the code

### Create an isolated environment (recommended)
- Windows
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1   # PowerShell
  # or
  .\.venv\Scripts\activate.bat   # cmd
  ```
- MacOS/Linux
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
  
### Install Python packages
With the virtualenv active:
```bash
pip install --upgrade pip
pip install mutagen wcwidth
```

### Run the App
With dependencies installed and your virtualenv active:
```bash
python musictui.py
```
(Replace musictui.py with the actual entrypoint filename if different.)

## Troubleshooting and Tips
- Permission errors on Linux/macOS: avoid `sudo pip install` inside a virtualenv. Use the virtualenv or `--user` for global installs.

- Multiple Python versions: use `python3` / `pip3` if python points to Python 2.

- Terminal rendering issues: ensure your terminal supports UTF‑8 and a monospace font; `wcwidth` helps with character widths.

- If mutagen import fails: confirm you installed into the same Python interpreter you run the script with: `python -m pip show mutagen`.

- Windows PowerShell execution policy: if activation fails, run PowerShell as admin and set Set-ExecutionPolicy RemoteSigned -Scope   CurrentUser.
  
