# Extract-Raspberry · API e monitor de desempenho

Monitor de recursos de uma Raspberry Pi, com dashboard em português, API JSON, histórico SQLite, autenticação e HTTPS opcionais. Não exige sensores externos ou serviços na nuvem.

A evolução do projeto foi feita para uma Raspberry Pi 4 de 4 GB com Debian 13 (trixie), ARM de 64 bits. Usa FastAPI, Uvicorn e psutil. O dashboard inicial foi confirmado na placa; autenticação e HTTPS passaram por testes locais, incluindo conexão TLS real. A instalação atualizada ainda precisa ser validada na Raspberry.

## Funcionalidades

- Dashboard com temperatura, CPU, RAM, disco da partição `/` e tempo ligada.
- Gráficos de temperatura, CPU e RAM: 1 hora, 24 horas, 7 dias e 30 dias.
- Coleta a cada ~5 segundos, gravação a cada ~30 segundos e retenção de ~30 dias.
- Coleta independente do navegador ou SSH e inicialização automática com systemd.
- Modo simples padrão: HTTP sem senha ou certificado, para a rede local.
- Modo protegido opcional: login HTTP Basic e token Bearer para integrações.
- No modo protegido: senha com PBKDF2, token como hash e HTTPS obrigatório.
- Certificado local gerado no dispositivo, sem domínio obrigatório.
- Interface Canvas sem CDN. A documentação interativa `/docs` usa assets externos do FastAPI.

Disco e tempo ligada aparecem nos cartões atuais, mas não são gravados no histórico.

## Instalar na Raspberry

Execute no SSH como usuário normal, **sem colocar sudo antes do instalador**. Estes comandos usam `main` após a integração da atualização:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
mkdir -p ~/src
git clone https://github.com/IsaacMartins12/Extract-Raspberry.git ~/src/monitor-rasp
cd ~/src/monitor-rasp
sh instalar.sh
```

Para testar a atualização antes do merge, após clonar use `git switch --track origin/modos-simples-protegido` antes de instalar.

O instalador prepara o ambiente virtual em `~/painel-rasp/.venv`, faz backup do código anterior e configura o início automático com systemd, preservando o histórico. Na primeira instalação, o padrão é **simples**, sem pedir senha ou gerar certificado. Em atualizações, o modo atual é preservado. Uma instalação protegida anterior sem `mode.json` também permanece protegida.

## Escolher ou trocar o modo

Na pasta do clone, execute como usuário normal:

```bash
# HTTP sem senha ou certificado
sh instalar.sh --mode simple

# HTTPS com usuário, senha e token de API
sudo apt install -y openssl
sh instalar.sh --mode protected
```

| Modo | Endereço | Credenciais e certificado |
| --- | --- | --- |
| Simples | `http://IP_DA_RASPBERRY:8080` | Não exige |
| Protegido | `https://IP_DA_RASPBERRY:8443` | Exige e configura na primeira ativação |

Ao ativar o modo protegido pela primeira vez, escolha usuário/senha (mínimo de 12 caracteres), guarde o token mostrado uma única vez e configure a confiança no certificado local, conforme o [guia de segurança](docs/seguranca.md). A troca de modo não apaga o banco, a senha, o token ou os certificados; reativar a proteção reaproveita a configuração anterior.

Rodar `sh instalar.sh` sem opções preserva o modo salvo. O modo é registrado em `~/painel-rasp/mode.json` e aplicado na unidade systemd por `--mode`. Não basta editar o JSON para alterar o processo em execução: execute o instalador. A pasta pessoal não deve conter espaços. Encerre processos manuais antes de usar a mesma porta.

Depois:

```bash
systemctl status painel-rasp --no-pager
hostname -I
```

Na instalação simples, acesse **`http://IP_DA_RASPBERRY:8080/`**. No modo protegido, use HTTPS em 8443 e informe as credenciais. O certificado local precisa ser confiado pelos clientes; não é reconhecido automaticamente por uma autoridade pública.

Aguarde cerca de um minuto pelos primeiros pontos. O histórico começa com a coleta e é local a cada instalação. Sem sensores extras: a temperatura vem de `/sys` na própria placa.

## Dashboard e API na mesma aplicação

As rotas são as mesmas nos dois modos. No simples, não exigem credenciais. No protegido, todas exigem HTTPS e senha ou token:

| Rota | Função |
| --- | --- |
| `/` | Dashboard, com login nativo do navegador |
| `/status` | API original: nova leitura a cada requisição (~1 segundo para CPU) |
| `/api` | Última leitura do coletor, sem nova coleta |
| `/api/history?period=24h` | Histórico; aceita `1h`, `24h`, `7d`, `30d` |
| `/docs` | Documentação interativa da API |
| `/openapi.json` | Esquema OpenAPI |

Os campos JSON originais de `/status` permanecem iguais. Ao escolher o modo protegido, atualize os consumidores da API para HTTPS, porta 8443 e autenticação. No simples, use HTTP em 8080.

No modo simples, consulte sem credenciais:

```bash
curl http://127.0.0.1:8080/status
curl "http://127.0.0.1:8080/api/history?period=24h"
```

No modo protegido, exemplo local usando senha: `curl` pede a senha interativamente. Use o usuário configurado e o IP incluído no certificado:

```bash
curl --cacert ~/painel-rasp/certs/cert.pem --user admin https://127.0.0.1:8443/status
```

Para automação no modo protegido, envie `Authorization: Bearer SEU_TOKEN` em um cabeçalho HTTP. Não envie token na URL. Veja exemplos sem gravar segredos no histórico do shell no [guia de segurança](docs/seguranca.md#consultar-com-token-de-api).

## Atualizar

No clone da Raspberry:

```bash
cd ~/src/monitor-rasp
git pull --ff-only
sh instalar.sh
```

O instalador não apaga o histórico, não troca automaticamente as credenciais e não muda o modo salvo sem uma escolha explícita. Ao trocar o modo, atualize o endereço dos seus clientes. Uma publicação no GitHub não atualiza a Raspberry automaticamente.

## Executar manualmente

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

O padrão manual é HTTP em 8080, sem carregar credenciais ou certificado. Para ativar proteção manualmente:

```bash
.venv/bin/python configurar_seguranca.py
.venv/bin/python server.py --mode protected
```

`python painel.py` inicia a mesma aplicação. A variável `EXTRACT_MODE=protected` também seleciona proteção; `--mode` tem prioridade. A configuração e o banco são lidos da pasta do código; um clone tem seus próprios arquivos, separados da instalação em `~/painel-rasp`. Se o serviço já ocupar a porta escolhida, pare-o antes do teste ou escolha outra porta com `--port`. Certificado e chave podem ser especificados com `--ssl-certfile` e `--ssl-keyfile`.

Use um único processo/worker para não duplicar coletores. No modo protegido, credenciais ou certificado/chave ausentes causam falha; o programa não recua automaticamente para o modo simples. Valores de modo inválidos também impedem o início.

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

Arquivos gerados: `mode.json` (modo da instalação), `auth.json` (hashes), `certs/` (certificado e chave privada), `historico.sqlite3` e auxiliares WAL/SHM, `.venv/` e `backup-*`. Todos ficam fora do Git; não publique cópias em outro formato.

## Limitações

O modo simples é para uma rede local de confiança: todos os aparelhos com acesso à porta podem consultar os dados. Não publique essa porta na internet. O modo protegido exige credenciais e cifra a conexão. HTTPS e senha não configuram um domínio, certificado público, firewall ou acesso pela internet. A proteção de tentativas é local, em memória, e não substitui uma defesa contra ataques distribuídos. O login Basic é guardado pelo navegador; não há botão de logout, contas múltiplas ou permissões por usuário. O token tem acesso de leitura às rotas protegidas.

O certificado local exige renovação manual antes de 365 dias e nova emissão se o endereço não estiver em seus SANs. A senha e o token não expiram automaticamente. O histórico mantém apenas amostras e médias: não registra todos os picos. Não há alertas, histórico de disco, análise por processo ou detecção de throttling.

## Guias

- [Arquitetura, cálculos e API](docs/arquitetura.md).
- [HTTPS, credenciais e token](docs/seguranca.md).
- [Manutenção, backup e problemas comuns](docs/operacao.md).
- [Desenvolvimento e GitHub](docs/github.md).

## Licença

[MIT](LICENSE), preservando o copyright original de Isaac Martins (2025).
