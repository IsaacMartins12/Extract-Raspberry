#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir="$HOME/painel-rasp"
mode=''
if [ "$#" -ne 0 ]; then
    if [ "$#" -ne 2 ] || [ "$1" != '--mode' ]; then
        printf '%s\n' 'Uso: sh scripts/instalar.sh [--mode simple|protected]' >&2
        exit 1
    fi
    mode="$2"
fi
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Execute como seu usuário normal, sem sudo antes do instalador.' >&2
    exit 1
fi
case "$target_dir" in
    *' '*) printf '%s\n' 'O caminho da instalação não pode conter espaços.' >&2; exit 1 ;;
esac
for file in extract_raspberry/app.py extract_raspberry/security.py extract_raspberry/web/index.html requirements/base.txt; do
    test -f "$source_dir/$file"
done
python3 -c 'import sqlite3'
if [ -z "$mode" ]; then
    if [ -f "$target_dir/config/mode.json" ]; then
        mode_file="$target_dir/config/mode.json"
    elif [ -f "$target_dir/mode.json" ]; then
        mode_file="$target_dir/mode.json"
    else
        mode_file=''
    fi
    if [ -n "$mode_file" ]; then
        mode=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mode"])' "$mode_file")
    elif [ -f "$target_dir/config/auth.json" ] || [ -f "$target_dir/auth.json" ]; then
        mode='protected'
    else
        mode='simple'
    fi
fi
case "$mode" in
    simple) port=8080; scheme=http ;;
    protected) port=8443; scheme=https; command -v openssl > /dev/null ;;
    *) printf '%s\n' 'Modo inválido. Use simple ou protected.' >&2; exit 1 ;;
esac
python3 -m compileall -q "$source_dir/extract_raspberry"
mkdir -p "$target_dir"
python3 -m venv "$target_dir/.venv"
"$target_dir/.venv/bin/python" -m pip install -r "$source_dir/requirements/base.txt"
backup_dir="$target_dir/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
for file in painel.py server.py security.py configurar_seguranca.py index.html requirements.txt; do
    if [ -f "$target_dir/$file" ]; then
        cp "$target_dir/$file" "$backup_dir/$file"
    fi
done
for folder in extract_raspberry scripts requirements; do
    if [ -d "$target_dir/$folder" ]; then
        cp -R "$target_dir/$folder" "$backup_dir/"
    fi
done
sudo -v
if sudo systemctl cat painel-rasp.service > "$backup_dir/painel-rasp.service" 2>/dev/null; then
    sudo systemctl stop painel-rasp.service
fi
# O serviço já está parado: a migração copia inclusive o WAL do banco antigo.
(cd "$source_dir" && "$target_dir/.venv/bin/python" -m extract_raspberry.migration --root "$target_dir")
if [ "$source_dir" != "$target_dir" ]; then
    cp -R "$source_dir/extract_raspberry" "$source_dir/scripts" "$source_dir/requirements" "$target_dir/"
fi
if [ "$mode" = 'protected' ]; then
    (cd "$target_dir" && .venv/bin/python -m extract_raspberry.configure_security)
fi
printf '{"mode":"%s"}\n' "$mode" > "$target_dir/config/mode.json"
sudo tee /etc/systemd/system/painel-rasp.service > /dev/null <<EOF
[Unit]
Description=Monitor Extract-Raspberry
After=network.target

[Service]
User=$(id -un)
WorkingDirectory=$target_dir
ExecStart=$target_dir/.venv/bin/python -m extract_raspberry --mode $mode --port $port
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now painel-rasp.service
sleep 2
sudo systemctl status painel-rasp.service --no-pager
printf '\nBackup do programa anterior: %s\n' "$backup_dir"
printf 'Modo: %s. Endereço: %s://IP_DA_RASPBERRY:%s\n' "$mode" "$scheme" "$port"
