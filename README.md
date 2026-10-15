# Catbox Uploader

A desktop app for uploading files to [catbox.moe](https://catbox.moe). Written in Python with Qt (PySide6).

## Features

- Upload multiple files with drag and drop, with progress and ETA.
- Upload anonymously or with your catbox userhash.
- Upload history with search, copy and open.
- Delete your own uploads from catbox.moe.
- Export the history (JSON, CSV, or URLs only) and import it back (JSON).
- Light and dark theme.

## Installation

Requires Python 3.10 or newer and Git.

### Windows

Install Python from [python.org](https://www.python.org/downloads/) and check **Add python.exe to PATH** during setup.

```powershell
git clone https://github.com/agb-777/catbox-uploader.git
cd catbox-uploader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Linux

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/agb-777/catbox-uploader.git
cd catbox-uploader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

To run it again later, use `.venv\Scripts\python main.py` (Windows) or `.venv/bin/python main.py` (Linux) from the project folder.

## Usage

1. Drop files into the **Upload** tab, or click **Add files**.
2. Click **Upload**.
3. Copy the links from the **History** tab.

To upload to your own account, paste your userhash in **Settings** and click **Apply**. Without it, uploads are anonymous and cannot be deleted from the app.

Files can be up to 200 MB.

## License

MIT
