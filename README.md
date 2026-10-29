# Extract-Raspberry · API e monitor de desempenho

Monitor de recursos de uma Raspberry Pi, com dashboard em português, API JSON, histórico SQLite, autenticação e HTTPS local. Não exige sensores externos ou serviços na nuvem.

A evolução do projeto foi feita para uma Raspberry Pi 4 de 4 GB com Debian 13 (trixie), ARM de 64 bits. Usa FastAPI, Uvicorn e psutil. O dashboard inicial foi confirmado na placa; autenticação e HTTPS passaram por testes locais, incluindo conexão TLS real. A instalação atualizada ainda precisa ser validada na Raspberry.

## Funcionalidades

- Dashboard com temperatura, CPU, RAM, disco da partição `/` e tempo ligada.
- Gráficos de temperatura, CPU e RAM: 1 hora, 24 horas, 7 dias e 30 dias.
- Coleta a cada ~5 segundos, gravação a cada ~30 segundos e retenção de ~30 dias.
- Coleta independente do navegador ou SSH e inicialização automática com systemd.
- Login HTTP Basic pelo próprio navegador e token Bearer para integrações.
- Senha protegida com PBKDF2; token armazenado como hash; HTTPS obrigatório.
- Certificado local gerado no dispositivo, sem domínio obrigatório.
- Interface Canvas sem CDN. A documentação interativa `/docs` usa assets externos do FastAPI.

Disco e tempo ligada aparecem nos cartões atuais, mas não são gravados no histórico.

## Instalar na Raspberry

Execute no SSH como usuário normal, **sem colocar sudo antes do instalador**. Estes comandos usam `main` após a integração da atualização:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git openssl
mkdir -p ~/src
git clone https://github.com/IsaacMartins12/Extract-Raspberry.git ~/src/monitor-rasp
cd ~/src/monitor-rasp
sh instalar.sh
```

Para testar a atualização antes do merge, após clonar use `git switch --track origin/autenticacao-https` antes de instalar.

O instalador prepara o ambiente virtual em `~/painel-rasp/.venv`, pede usuário e senha com pelo menos 12 caracteres, mostra um token de API uma única vez e gera um certificado válido por 365 dias. Guarde o token em um gerenciador de senhas. Não compartilhe o terminal ou seus logs nesse passo.

Ele faz backup dos arquivos de código anteriores, preserva `historico.sqlite3` e configura o serviço `painel-rasp` na porta **8443**. Nas reinstalações, mantém as credenciais e o certificado existentes. Se estiver executando o programa manualmente, encerre-o antes de instalar. A pasta pessoal não deve conter espaços.

Depois:

```bash
systemctl status painel-rasp --no-pager
hostname -I
```

Acesse **`https://IP_DA_RASPBERRY:8443/`**. O navegador solicitará usuário e senha. Como o certificado é local, é necessário estabelecer confiança nele nos aparelhos clientes; veja o [guia de segurança](docs/seguranca.md). HTTPS cifra a conexão, mas um certificado autoassinado não comprova a identidade sem essa verificação.

Aguarde cerca de um minuto pelos primeiros pontos. O histórico começa com a coleta e é local a cada instalação. Sem sensores extras: a temperatura vem de `/sys` na própria placa.

## Dashboard e API na mesma aplicação

Todas as rotas exigem HTTPS e credenciais:

| Rota | Função |
| --- | --- |
| `/` | Dashboard, com login nativo do navegador |
| `/status` | API original: nova leitura a cada requisição (~1 segundo para CPU) |
| `/api` | Última leitura do coletor, sem nova coleta |
| `/api/history?period=24h` | Histórico; aceita `1h`, `24h`, `7d`, `30d` |
| `/docs` | Documentação interativa da API |
| `/openapi.json` | Esquema OpenAPI |

Os campos JSON originais de `/status` permanecem iguais. Autenticação, HTTPS e a mudança de porta são alterações obrigatórias na forma de acesso. Integrações antigas precisam ser atualizadas.

Exemplo local usando senha: `curl` pede a senha interativamente. Use o usuário configurado e o IP incluído no certificado:

```bash
curl --cacert ~/painel-rasp/certs/cert.pem --user admin https://127.0.0.1:8443/status
```

Para automação, envie `Authorization: Bearer SEU_TOKEN` em um cabeçalho HTTP. Não envie token na URL. Veja exemplos sem gravar segredos no histórico do shell no [guia de segurança](docs/seguranca.md#consultar-com-token-de-api).

## Atualizar

No clone da Raspberry:

```bash
cd ~/src/monitor-rasp
git pull --ff-only
sh instalar.sh
```

O instalador não apaga o histórico nem troca automaticamente a senha ou o token. O endereço anterior `http://IP:8080` deixa de funcionar; use HTTPS em 8443 e atualize seus consumidores da API. Uma publicação no GitHub não atualiza a Raspberry automaticamente.

## Executar manualmente

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python configurar_seguranca.py
.venv/bin/python server.py
```

O padrão agora é HTTPS em 8443. `python painel.py` inicia a mesma aplicação. A configuração e o banco são lidos da pasta do código; um clone tem seus próprios arquivos, separados da instalação em `~/painel-rasp`. Se o serviço já ocupar 8443, pare-o antes do teste ou escolha outra porta com `--port`. Certificado e chave podem ser especificados com `--ssl-certfile` e `--ssl-keyfile`.

Use um único processo/worker para não duplicar coletores. A execução sem credenciais válidas ou sem certificado/chave falha em vez de abrir acesso sem proteção. Não há modo HTTP anônimo nesta versão.

## Operação

```bash
systemctl status painel-rasp --no-pager
journalctl -u painel-rasp -n 50 --no-pager
sudo systemctl restart painel-rasp
sudo systemctl stop painel-rasp
sudo systemctl start painel-rasp
```

Fechar o SSH ou o navegador não para o serviço. Reiniciar a Pi retoma a coleta com o banco anterior. Desligada, ela não coleta. Os gráficos separam lacunas grandes; pequenas interrupções podem ficar ocultas na agregação.

## Verificação do código

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile server.py painel.py security.py configurar_seguranca.py
sh -n instalar.sh
```

Os testes cobrem API original, persistência, retenção, agregação, autenticação, bloqueio HTTP e handshake HTTPS real. O teste TLS requer `openssl` no PATH; caso ausente, é marcado como ignorado. Os testes não substituem a validação no hardware e do systemd real.

## Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| `server.py` | FastAPI, rotas, proteção e execução HTTPS |
| `painel.py` | Coleta Linux e histórico SQLite |
| `security.py` | Verificação de senha/token e limitação de tentativas |
| `configurar_seguranca.py` | Configurar credenciais e certificado local |
| `index.html` | Dashboard e gráficos Canvas |
| `instalar.sh` | Ambiente virtual, instalação e systemd |
| `requirements.txt`, `requirements-dev.txt` | Dependências da aplicação e dos testes |
| `tests/` | Testes automatizados |
| `docs/` | Arquitetura, segurança, operação e publicação |

Arquivos gerados: `auth.json` (hashes), `certs/` (certificado e chave privada), `historico.sqlite3` e auxiliares WAL/SHM, `.venv/` e `backup-*`. Todos ficam fora do Git; não publique cópias em outro formato.

## Limitações

A instalação padrão é para sua rede local. HTTPS e senha não configuram um domínio, certificado público, firewall ou acesso pela internet. A proteção de tentativas é local, em memória, e não substitui uma defesa contra ataques distribuídos. O login Basic é guardado pelo navegador; não há botão de logout, contas múltiplas ou permissões por usuário. O token tem acesso de leitura às rotas protegidas.

O certificado local exige renovação manual antes de 365 dias e nova emissão se o endereço não estiver em seus SANs. A senha e o token não expiram automaticamente. O histórico mantém apenas amostras e médias: não registra todos os picos. Não há alertas, histórico de disco, análise por processo ou detecção de throttling.

## Guias

- [Arquitetura, cálculos e API](docs/arquitetura.md).
- [HTTPS, credenciais e token](docs/seguranca.md).
- [Manutenção, backup e problemas comuns](docs/operacao.md).
- [Desenvolvimento e GitHub](docs/github.md).

## Licença

[MIT](LICENSE), preservando o copyright original de Isaac Martins (2025).
