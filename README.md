# MusicTui
A TUI music player written in Python that plays music directly from your local files. 

## Features
* Play media formats
  
  * MP3, FLAC, OGG, WAV, AAC, M4A, Opus, WMA, APE
  * Extra: AC3, DTS, TrueHD, AMR, AIFF
    
* Search your library
* Customizable color theme
* Skip forward/backward 10 seconds
* Volume control
* Shuffle mode

## Dependencies
* Python 3.8+
* mpv

## Installation
Install Dependencies
* Arch Linux
  
  `sudo pacman -S python python-pip mpv ffmpeg`
* Ubuntu/Debian
  
  `sudo apt install python3 python3-pip mpv ffmpeg`
* macOS
  
  `brew install python mpv ffmpeg`
* Windows (WSL2)
  
  `sudo apt install python3 python3-pip mpv ffmpeg`
  
Install MusicTui
`git clone https://github.com/yourusername/term-music.git`
`cd term-music`
`pip install -e .`
