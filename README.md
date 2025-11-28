# GenMaps Downloader — Generals Zero Hour

A fast, multi-threaded downloader for Command & Conquer: Generals Zero Hour custom maps from [CNC Labs](https://www.cnclabs.com).

## Features

- **GUI & CLI**: Beautiful Tkinter GUI styled after Generals Zero Hour, plus a command-line interface.
- **Multi-threaded**: Parallel downloads (configurable workers) for speed.
- **Retry logic**: Exponential backoff with jitter for rate limits and server errors.
- **Progress tracking**: Real-time per-map progress bars and download logs.
- **Configurable**: Choose player count, max pages, worker threads, and download directory.
- **Stop/Cancel**: Graceful pause and stop controls during download.

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone or extract** this project folder.

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Convert icon to `.ico`** (optional but recommended for exe build):
```bash
python -c 'from PIL import Image; Image.open("assets/icon.png").save("assets/icon.ico", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])'
```

## Usage

### GUI (Recommended)

```bash
python cncgui.py
```

- Set number of players (2–8)
- Set max pages to scrape (1–100)
- Set parallel downloads (1–10)
- Choose download directory
- Click **START DOWNLOAD**

### CLI

```bash
python cnclabsCLI.py -p 8 -m 10 -w 3 -d downloads
```

**Options**:
- `-p, --players`: Number of players (default: 8)
- `-m, --max-pages`: Maximum pages to scrape (default: 10)
- `-w, --workers`: Parallel download workers (default: 3)
- `-d, --dir`: Download directory (default: downloads)

## Building an Executable (PyInstaller)

### Quick Build

```powershell
pip install pyinstaller

pyinstaller --noconfirm --onedir --windowed --name GenMapsDownloader `
  --icon=assets\icon.ico `
  --add-data "assets;assets" `
  cncgui.py
```

Executable will be at: `dist\GenMapsDownloader\GenMapsDownloader.exe`

### One-File Executable (Larger but portable)

```powershell
pyinstaller --noconfirm --onefile --windowed --name GenMapsDownloader `
  --icon=assets\icon.ico `
  --add-data "assets;assets" `
  cncgui.py
```

Executable will be at: `dist\GenMapsDownloader.exe`

## Project Structure

```
GenMapsDownloader/
├── cncgui.py              # Main GUI application
├── cnclabsCLI.py          # CLI downloader class
├── cncmaps.py             # Alternate downloader variant
├── requirements.txt       # Python dependencies
├── assets/
│   ├── icon.png           # App icon (PNG)
│   ├── icon.ico           # App icon (Windows)
│   └── logo.png           # Generated emblem/logo
├── downloads/             # Default download folder (created on first run)
└── README.md              # This file
```

## Dependencies

- `requests` — HTTP client
- `beautifulsoup4` — HTML parsing
- `lxml` — XML/HTML parser backend
- `pillow` — Image handling
- `colorama` — Terminal colors (CLI)

See `requirements.txt` for pinned versions.

## Troubleshooting

### "Icon file not found" warning
Ensure `assets/icon.png` or `assets/icon.jpg` exists in the same folder as the script.

### Maps not downloading
- Check your internet connection.
- Verify the CNC Labs website is accessible.
- Try reducing the max pages or increasing the retry wait time in code.

### PyInstaller build issues
- Missing modules: add `--hidden-import modulename` to the PyInstaller command.
- Antivirus blocks exe: mark the build as safe or test on another machine.
- Asset paths: the exe automatically bundles the `assets/` folder; no extra setup needed.

## License

This tool is for personal use and educational purposes. Command & Conquer is a trademark of Westwood Studios / Virgin Interactive.

## Contributing

Issues and pull requests welcome. Please test thoroughly before submitting.

---

**Enjoy downloading and playing your favorite Generals Zero Hour custom maps!** ⚔️
