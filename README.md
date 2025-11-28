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

## Usage

### GUI

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


## Dependencies

See `requirements.txt` for pinned versions.


### Maps not downloading
- Check your internet connection.
- Verify the CNC Labs website is accessible.
- Try reducing the max pages or increasing the retry wait time in code.


## License

This tool is for personal use and educational purposes. Command & Conquer is a trademark of Westwood Studios / Virgin Interactive.

## Contributing

Issues and pull requests welcome. Please test thoroughly before submitting.

---

**Enjoy downloading and playing your favorite Generals Zero Hour custom maps!** ⚔️

