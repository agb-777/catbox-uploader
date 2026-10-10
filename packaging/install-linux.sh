#!/bin/sh
# Installs the menu entry + icon for the current user (needed for the icon on Wayland).
# Usage: packaging/install-linux.sh [python-executable]   (default: python3)
set -eu

here=$(cd "$(dirname "$0")" && pwd)
[ -f "$here/../main.py" ] || { echo "main.py not found"; exit 1; }
main="$(cd "$here/.." && pwd)/main.py"

# Absolute path of the interpreter WITHOUT resolving symlinks: .venv/bin/python is a symlink,
# and resolving it would silently drop the virtual environment.
py=${1:-python3}
case "$py" in
    */*) ;;
    *) py=$(command -v "$py") || { echo "Python not found: $py"; exit 1; } ;;
esac
[ -x "$py" ] || { echo "Python not found: $py"; exit 1; }
case "$py" in
    /*) ;;
    *) py="$(cd "$(dirname "$py")" && pwd)/$(basename "$py")" ;;
esac

for p in "$py" "$main"; do
    case "$p" in
        *\\*|*'
'*) echo "Unsupported character in path: $p"; exit 1 ;;
    esac
done

# Quote one argument for a .desktop Exec line (spaces, quotes, $, backticks, %).
quote() {
    printf '"%s"' "$(printf '%s' "$1" | sed -e 's/[\"`$]/\\&/g' -e 's/%/%%/g')"
}

apps="$HOME/.local/share/applications"
icons="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$apps" "$icons"
cp "$here/catbox-uploader.png" "$icons/catbox-uploader.png"
{
    printf '[Desktop Entry]\n'
    printf 'Type=Application\n'
    printf 'Name=Catbox Uploader\n'
    printf 'Exec=%s %s\n' "$(quote "$py")" "$(quote "$main")"
    printf 'Icon=catbox-uploader\n'
    printf 'Terminal=false\n'
    printf 'Categories=Network;Utility;\n'
    printf 'StartupWMClass=catbox-uploader\n'
} > "$apps/catbox-uploader.desktop"

update-desktop-database "$apps" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Installed. Restart the app."
