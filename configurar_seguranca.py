"""Configuração interativa; não recebe senhas ou tokens na linha de comando."""
import argparse
import getpass
import ipaddress
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from security import Authentication, credentials

ROOT = Path(__file__).resolve().parent


def certificate(cert, key, hosts):
    names = {'DNS:localhost', 'IP:127.0.0.1', 'IP:::1'}
    for host in hosts:
        try:
            names.add('IP:' + str(ipaddress.ip_address(host)))
        except ValueError:
            if not host or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in host):
                raise ValueError('Nome de rede inválido: ' + host)
            names.add('DNS:' + host)
    cert.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Gere em uma pasta temporária e só substitua após sucesso do OpenSSL.
    with tempfile.TemporaryDirectory(dir=cert.parent) as folder:
        folder = Path(folder)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes',
            '-sha256', '-days', '365', '-keyout', str(folder / 'key.pem'),
            '-out', str(folder / 'cert.pem'), '-subj', '/CN=Extract-Raspberry',
            '-addext', 'subjectAltName=' + ','.join(sorted(names)),
            '-addext', 'basicConstraints=critical,CA:FALSE',
            '-addext', 'keyUsage=critical,digitalSignature,keyEncipherment',
            '-addext', 'extendedKeyUsage=serverAuth'], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        os.chmod(folder / 'key.pem', 0o600)
        os.replace(folder / 'key.pem', key)
        os.replace(folder / 'cert.pem', cert)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-auth', action='store_true', help='Trocar usuário, senha e token')
    parser.add_argument('--renew-cert', action='store_true', help='Gerar novo certificado local')
    args = parser.parse_args()
    os.umask(0o077)
    path = ROOT / 'auth.json'
    if not path.exists() or args.reset_auth:
        user = input('Usuário do painel [admin]: ').strip() or 'admin'
        password = getpass.getpass('Senha (mínimo 12 caracteres): ')
        if password != getpass.getpass('Repita a senha: '):
            raise SystemExit('As senhas não coincidem; nenhuma credencial foi alterada.')
        data, token = credentials(user, password)
        Authentication(data)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=ROOT,
                                         prefix='.auth-', delete=False) as output:
            json.dump(data, output)
            temporary = Path(output.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        print('\nGuarde o token de API em um gerenciador de senhas. Ele só aparece agora:')
        print(token)
        print('A senha e o token não serão salvos em texto puro.\n')
    else:
        Authentication(json.loads(path.read_text(encoding='utf-8')))
        print('Credenciais existentes preservadas.')
    cert, key = ROOT / 'certs/cert.pem', ROOT / 'certs/key.pem'
    if args.renew_cert or not (cert.exists() and key.exists()):
        hosts = {socket.gethostname(), socket.gethostname() + '.local'}
        try:
            hosts.update(subprocess.check_output(['hostname', '-I'], text=True).split())
        except (OSError, subprocess.CalledProcessError):
            pass
        extra = input('IP ou hostname adicional para o certificado (Enter para automático): ').strip()
        if extra:
            hosts.add(extra)
        certificate(cert, key, hosts)
        print('Certificado local criado, válido por 365 dias.')
    print('Configuração concluída. Reinicie o serviço para aplicar alterações.')


if __name__ == '__main__':
    main()
