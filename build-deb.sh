#!/bin/bash
set -e

VERSION="3.1.0"
PACKAGE="screenglow"
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build/$PACKAGE"

rm -rf "$BUILD"

mkdir -p "$BUILD/DEBIAN"
mkdir -p "$BUILD/usr/lib/screenglow"
mkdir -p "$BUILD/usr/bin"
mkdir -p "$BUILD/usr/share/applications"
mkdir -p "$BUILD/usr/share/icons/hicolor/scalable/apps"

install -m 644 "$ROOT/screenglow_3.1.0_english.py" \
    "$BUILD/usr/lib/screenglow/screenglow.py"

install -m 755 "$ROOT/screenglow" \
    "$BUILD/usr/bin/screenglow"

install -m 644 "$ROOT/screenglow.desktop" \
    "$BUILD/usr/share/applications/screenglow.desktop"

install -m 644 "$ROOT/screenglow.svg" \
    "$BUILD/usr/share/icons/hicolor/scalable/apps/screenglow.svg"

cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: screenglow
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Maintainer: srdjanbaic
Depends: python3, python3-pyqt6, python3-pynput, ffmpeg, pulseaudio-utils, x11-xserver-utils
Description: Screen recorder with cursor highlight
 ScreenGlow is a desktop screen recording application
 featuring microphone recording and visual cursor effects.
CONTROL

dpkg-deb --build --root-owner-group "$BUILD" \
    "$ROOT/${PACKAGE}_${VERSION}_all.deb"
