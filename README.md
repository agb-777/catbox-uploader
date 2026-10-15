## Instalasi

### Persyaratan

- [Python](https://www.python.org/downloads/) 3.10 atau lebih baru
- [Git](https://git-scm.com/downloads)

### Windows

> [!NOTE]
> Pastikan Python sudah terinstal di komputer kamu. Jika belum, unduh di [python.org/downloads](https://www.python.org/downloads/) dan **centang "Add python.exe to PATH"** saat instalasi.

```powershell
git clone https://github.com/agb-777/catbox-uploader.git
cd catbox-uploader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> [!TIP]
> Jika `activate` ditolak karena execution policy, jalankan sekali:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Linux (Debian / Ubuntu)

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

> [!NOTE]
> Untuk distro lain, instal paket yang setara: `dnf install python3 python3-pip git` (Fedora) atau `pacman -S python python-pip git` (Arch).

### Menjalankan Lagi

Setelah instalasi, cukup jalankan perintah ini dari folder proyek:

```powershell
# Windows
.venv\Scripts\python main.py
```

```bash
# Linux
.venv/bin/python main.py
```
