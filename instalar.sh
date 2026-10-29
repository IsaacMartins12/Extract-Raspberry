#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target_dir="$HOME/painel-rasp"
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Execute como seu usuário normal: sh instalar.sh (sem sudo).' >&2
    exit 1
fi
case "$target_dir" in
    *' '*) printf '%s\n' 'O caminho da instalação não pode conter espaços.' >&2; exit 1 ;;
esac
test -f "$source_dir/index.html"
test -f "$source_dir/server.py"
test -f "$source_dir/requirements.txt"
test -f "$source_dir/security.py"
test -f "$source_dir/configurar_seguranca.py"
command -v openssl > /dev/null
python3 -c 'import sqlite3'
python3 -m py_compile "$source_dir/painel.py" "$source_dir/server.py" "$source_dir/security.py" "$source_dir/configurar_seguranca.py"
mkdir -p "$target_dir"
# Prepare as dependências antes de interromper o serviço atual.
python3 -m venv "$target_dir/.venv"
"$target_dir/.venv/bin/python" -m pip install -r "$source_dir/requirements.txt"
backup_dir="$target_dir/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
for file in painel.py server.py security.py configurar_seguranca.py index.html requirements.txt; do
    if [ -f "$target_dir/$file" ]; then
        cp "$target_dir/$file" "$backup_dir/$file"
    fi
done
sudo -v
if [ "$source_dir" != "$target_dir" ]; then
    cp "$source_dir/security.py" "$source_dir/configurar_seguranca.py" "$target_dir/"
fi
# Configuração interativa antes de parar a versão instalada.
"$target_dir/.venv/bin/python" "$target_dir/configurar_seguranca.py"
if sudo systemctl cat painel-rasp.service > /dev/null 2>&1; then
    sudo systemctl stop painel-rasp.service
fi
if [ "$source_dir" != "$target_dir" ]; then
    cp "$source_dir/painel.py" "$source_dir/server.py" "$source_dir/index.html" "$source_dir/requirements.txt" "$target_dir/"
fi
sudo tee /etc/systemd/system/painel-rasp.service > /dev/null <<EOF
[Unit]
Description=Painel da Raspberry Pi com historico
After=network.target

[Service]
User=$(id -un)
WorkingDirectory=$target_dir
ExecStart=$target_dir/.venv/bin/python $target_dir/server.py --port 8443
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
