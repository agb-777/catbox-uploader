```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip libxcb-cursor0 libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3 libsecret-1-0 gnome-keyring
git clone https://github.com/agb-777/catbox-uploader
cd catbox-uploader
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```
