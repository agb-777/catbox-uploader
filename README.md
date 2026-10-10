# Catbox Uploader

Desktop app for uploading files to [catbox.moe](https://catbox.moe), written in Python with PySide6.
Unofficial, not affiliated with catbox.moe.

- Upload several files in one queue (file picker or drag and drop)
- Upload anonymously or with your userhash
- Upload history with search, export (JSON, CSV, TXT) and import
- Delete your uploaded files from catbox.moe

## Install

Requires Python 3.9 or newer.

```bash
git clone https://github.com/agb-777/catbox-uploader.git
cd catbox-uploader
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

On Linux with Wayland the window icon only shows up if the app has a menu entry. Run this once:

```bash
packaging/install-linux.sh .venv/bin/python
```

## Usage

1. **Upload** tab: click *Add files* (or drop files into the window), then *Upload*.
2. **History** tab: your uploads and their links. Select a row and click *Copy URL*.
3. **Settings** tab: paste your userhash (shown on your catbox.moe account page) and click *Apply*.
   With a userhash, uploads are tied to your account and can be deleted from the app
   (*History* > *Delete from Catbox*, permanent). Without one, uploads are anonymous and cannot be deleted.

Catbox accepts about 200 MB per file and rejects `.exe`, `.scr`, `.cpl`, `.jar`, `.doc`, `.docx` and `.docm`.

Settings and history are saved in `~/.catbox_uploader.json`. The userhash goes to the system keychain
when the `keyring` package can reach one, otherwise it is kept in that file (owner-only permissions).

## Credits

- [catbox.moe](https://catbox.moe) for the file hosting and API
- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/), [requests](https://requests.readthedocs.io/),
  [requests-toolbelt](https://github.com/requests/toolbelt) and [keyring](https://github.com/jaraco/keyring)
- Author: [agb-777](https://github.com/agb-777)

## License

[MIT](LICENSE)
