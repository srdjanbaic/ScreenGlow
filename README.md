# ScreenGlow

**ScreenGlow** is a desktop screen recording application for Linux, featuring visual cursor highlighting and mouse click effects.

## Features

- Desktop screen recording with FFmpeg
- Multiple recording resolutions
- 15, 30 and 60 FPS recording options
- Microphone and audio source selection
- Customizable cursor halo effect
- Animated left and right mouse click effects
- Adjustable cursor effect color, size, intensity and speed
- Pause and resume recording
- Recording timer
- Preview of the latest recording
- Quick access to the Videos folder
- Dark user interface

## Requirements

- Debian 13 or compatible Linux distribution
- Python 3
- PyQt6
- pynput
- FFmpeg
- PulseAudio utilities
- X11 utilities

## Installation

Download the latest `.deb` package from the GitHub Releases page.

Install it with:

    sudo apt install ./screenglow_3.1.0_all.deb

Launch ScreenGlow:

    screenglow

## Building from source

Clone the repository:

    git clone https://github.com/srdjanbaic/ScreenGlow.git
    cd ScreenGlow

Build the Debian package:

    chmod +x build-deb.sh
    ./build-deb.sh

## Uninstallation

    sudo apt remove screenglow

## License

ScreenGlow is released under the MIT License.
See the LICENSE file for details.
