# Operação e manutenção

## Da primeira versão ao histórico

O projeto foi montado por SSH. Primeiro foram consultados `cat /etc/os-release` e `uname -m`, identificando Debian 13 em ARM de 64 bits. A primeira versão lia métricas sob demanda e servia uma página HTTP na porta 8080; o modo protegido usa HTTPS em 8443 e o simples mantém HTTP em 8080. Depois foi configurado um serviço systemd, para continuar funcionando após fechar o SSH e voltar no boot.

A versão atual separa a coleta da abertura da página: um coletor executa continuamente, grava histórico SQLite e a interface consulta esse histórico para desenhar gráficos. Não foi necessário conectar sensores externos; a temperatura vem do sistema da própria placa.

## Transferir do Windows para a Raspberry

Este procedimento permite atualizar a instalação existente sem depender de um clone na Raspberry. Na janela do **PowerShell do computador Windows**, entre na pasta local do projeto. Ajuste o caminho, o usuário e o endereço da placa:

```powershell
cd C:\Users\USER\Documents\rasp_2026\Extract-Raspberry
ssh pi@IP_DA_RASPBERRY "mkdir -p ~/painel-rasp-atualizacao"
scp server.py painel.py security.py configurar_seguranca.py index.html requirements.txt instalar.sh pi@IP_DA_RASPBERRY:painel-rasp-atualizacao/
```

Depois, no **SSH da Raspberry**:

```bash
sudo apt update
sudo apt install -y python3-venv
# Para instalar no modo protegido, também instale openssl.
sh ~/painel-rasp-atualizacao/instalar.sh
```

Se a versão manual estiver ocupando o terminal e a porta escolhida (8080 ou 8443), encerre-a com `Ctrl+C` antes da instalação. Após atualizar, pressione `Ctrl+F5` no navegador.

O instalador desta versão funciona tanto com o serviço existente quanto em uma primeira instalação. Ele deve ser executado como usuário normal, sem prefixar `sudo`.

## Serviço e diagnóstico

```bash
systemctl status painel-rasp --no-pager
sudo systemctl restart painel-rasp
sudo systemctl stop painel-rasp
sudo systemctl start painel-rasp

# Logs recentes e acompanhamento contínuo (Ctrl+C encerra só o acompanhamento)
journalctl -u painel-rasp -n 50 --no-pager
journalctl -u painel-rasp -f

# Configuração efetiva
systemctl cat painel-rasp
```

Para impedir o início automático e parar o monitor:

```bash
sudo systemctl disable --now painel-rasp
```

Para reativar:

```bash
sudo systemctl enable --now painel-rasp
```

Para alterar manualmente a unidade em `/etc/systemd/system/painel-rasp.service`, rode depois `sudo systemctl daemon-reload` e `sudo systemctl restart painel-rasp`. O instalador recria essa unidade a cada execução; registre personalizações antes de reinstalar.

## Backup consistente do histórico

O banco usa WAL, então copiar apenas o arquivo `.sqlite3` enquanto o serviço escreve pode omitir transações. Use a API de backup do SQLite abaixo; ela cria uma cópia consistente com o serviço rodando:

```bash
python3 - <<'PY'
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

source = Path.home() / 'painel-rasp' / 'historico.sqlite3'
if not source.is_file():
    raise SystemExit('Banco não encontrado: ' + str(source))
folder = Path.home() / 'backups-painel'
folder.mkdir(exist_ok=True)
target = folder / ('historico-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
    with closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
print(target)
PY
```

Copie o backup para outro dispositivo se precisar sobreviver à perda do cartão. Não envie o histórico ao GitHub. Para restaurar, pare o serviço, preserve o banco atual e seus arquivos auxiliares em outra pasta e coloque a cópia consistente em `~/painel-rasp/historico.sqlite3`, com permissão de escrita para o usuário do serviço. Inicie novamente e consulte os logs. A rotina de retenção volta a remover amostras com mais de 30 dias.

## Voltar ao programa anterior

O instalador informa a pasta `~/painel-rasp/backup-AAAAMMDD-HHMMSS`. Para restaurar o código, substitua a data abaixo pela pasta real:

```bash
sudo systemctl stop painel-rasp
cp ~/painel-rasp/backup-AAAAMMDD-HHMMSS/painel.py ~/painel-rasp/painel.py
```

Se essa pasta também tiver `server.py` e `requirements.txt`, restaure-os:

```bash
cp ~/painel-rasp/backup-AAAAMMDD-HHMMSS/server.py ~/painel-rasp/server.py
cp ~/painel-rasp/backup-AAAAMMDD-HHMMSS/requirements.txt ~/painel-rasp/requirements.txt
```

Se essa pasta também tiver `index.html`, restaure-o:

```bash
cp ~/painel-rasp/backup-AAAAMMDD-HHMMSS/index.html ~/painel-rasp/index.html
```

Se o backup contém `security.py` e `configurar_seguranca.py`, restaure também esses arquivos antes de iniciar. Não substitua `auth.json` ou os certificados ao restaurar apenas o código.

Depois de conferir a unidade adequada à versão restaurada:

```bash
sudo systemctl start painel-rasp
systemctl status painel-rasp --no-pager
```

Ao voltar à versão anterior que executava apenas `painel.py`, altere também o `ExecStart` da unidade para `/usr/bin/python3 /home/SEU_USUARIO/painel-rasp/painel.py`, usando o caminho real, rode `sudo systemctl daemon-reload` e reinicie o serviço. O programa original mais antigo tinha o HTML embutido e não gravava histórico. O backup do instalador não inclui a unidade systemd nem as dependências do ambiente virtual; uma reversão completa deve considerar ambos. Não apague o banco para restaurar o código.

## Problemas comuns

| Sintoma | O que verificar |
| --- | --- |
| Página não abre | Serviço ativo, `hostname -I`, porta escolhida (8080 ou 8443) e conectividade entre os aparelhos |
| Endereço deixou de funcionar após reboot | IP pode ter mudado; confira novamente ou configure reserva DHCP no roteador |
| `Address already in use` | Outra instância ocupa a porta: `sudo ss -ltnp 'sport = :8443'`; encerre a instância manual correta |
| Gráfico vazio após instalar | Aguarde cerca de um minuto; a coleta começa na instalação |
| Gráfico não atualiza | Confira mensagem da página, timestamps e logs do serviço |
| Temperatura indisponível | Confira `cat /sys/class/thermal/thermal_zone0/temp` |
| CPU em 0% | Pode refletir baixa atividade; confira várias leituras e compare com `top` |
| Erro de permissão no banco | Verifique o usuário da unidade e `ls -l ~/painel-rasp`; evite executar manualmente com sudo |
| Erro de disco cheio | Confira `df -h /` e os logs; gravações precisam de espaço disponível |
| `No module named fastapi` ou `psutil` | Execute pelo Python da `.venv` ou rode novamente o instalador |
| Falha ao criar o ambiente virtual | Instale `python3-venv` e confira espaço e permissões |
| Erro envolvendo `\r` no instalador | Salve `instalar.sh` com finais de linha LF; o repositório inclui `.gitattributes` |
| Tela antiga após atualizar | Use `Ctrl+F5` e confirme que instalou a partir da pasta certa |

Se necessário, instale `curl` para verificar a API: `sudo apt install -y curl`. Consulte `curl --cacert ~/painel-rasp/certs/cert.pem --user admin https://127.0.0.1:8443/api`. Verifique também a hora com `date`; timestamps incorretos prejudicam o histórico.

## Uso contínuo

Você pode fechar o navegador e sair do SSH. O serviço segue coletando enquanto a Raspberry estiver ligada. Uma reinicialização normal volta a iniciar o monitor. As gravações usam o armazenamento da própria placa; mantenha alimentação estável e backup quando o histórico for importante.

No modo protegido, o servidor exige credenciais e HTTPS. No simples, o acesso é HTTP sem autenticação e deve ficar restrito à rede de confiança. O certificado local precisa ser verificado e confiado pelos clientes; veja `seguranca.md`. Não exponha a porta no roteador sem projetar o acesso remoto e o controle de rede.

## Migrar a API antiga para o serviço

`/status` continua disponível e coleta a cada requisição, com o JSON original. No simples, use `http://IP_DA_RASPBERRY:8080/status`, sem credenciais. No protegido, use `https://IP_DA_RASPBERRY:8443/status`, validando o certificado e enviando usuário/senha ou token Bearer. Só o endereço do modo selecionado fica ativo.

O histórico já existente em `~/painel-rasp/historico.sqlite3` é reaproveitado; a estrutura da tabela não mudou. Nenhuma alteração chega automaticamente à placa quando o código é publicado no GitHub. Transfira os arquivos ou atualize o clone e execute o instalador.

As credenciais e os certificados são locais e não fazem parte do backup de código do instalador. Guarde uma cópia privada protegida de `auth.json` e da chave se precisar recuperar essa identidade. Trocar senha/token não altera os dados históricos. Ao restaurar uma versão anterior ao suporte de segurança, não reutilize sua configuração de serviço como se ela ainda garantisse autenticação e TLS; prefira manter a versão protegida.

## Trocar entre os modos

Na pasta do clone, use `sh instalar.sh --mode simple` para HTTP sem senha, ou `sh instalar.sh --mode protected` para HTTPS com autenticação (exige OpenSSL). O instalador reinicia o serviço na porta adequada e preserva o histórico e as credenciais. Rodar sem opção mantém o modo atual. Não é preciso desinstalar nem apagar certificados para voltar ao modo simples.
