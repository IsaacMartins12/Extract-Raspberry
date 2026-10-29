# HTTPS, login e API

## Primeira configuração

O instalador pede usuário e senha (mínimo de 12 caracteres), sem exibir a senha digitada. O login do dashboard é HTTP Basic: uma janela nativa do navegador pede as credenciais. Não há formulário de cadastro ou banco de usuários. Há apenas uma identidade por instalação.

Um token de API aleatório é mostrado uma única vez no terminal. Guarde-o em um gerenciador de senhas. `auth.json` contém apenas hashes, salt e nome do usuário, e é criado com permissão `0600` no Linux. A chave TLS privada também tem `0600`; a pasta `certs` é criada com `0700`.

Na reinstalação, os arquivos existentes são preservados. Nunca envie `auth.json`, tokens, senhas ou `certs/key.pem` ao GitHub. O `.gitignore` os exclui, mas isso não protege arquivos já rastreados ou cópias com outro nome.

## Certificado local e confiança

O programa de configuração usa OpenSSL para gerar um certificado autoassinado válido por 365 dias. Os SANs incluem localhost, os endereços de loopback, o hostname da placa, seu nome `.local` e os IPs retornados por `hostname -I`. Você pode informar mais um endereço no prompt. O certificado não é reconhecido automaticamente por autoridades públicas.

Para acessar por IP, use um IP incluído nesses SANs. Uma reserva DHCP no roteador evita mudanças de endereço. Um certificado confiável precisa tanto ser reconhecido pelo cliente quanto corresponder ao nome ou IP acessado.

Copie **somente o certificado público** para o computador por um canal já confiável, como a conexão SSH cuja identidade você verificou. Exemplo no PowerShell:

```powershell
scp pi@IP_DA_RASPBERRY:painel-rasp/certs/cert.pem .\raspberry-cert.pem
```

Confira a impressão digital SHA-256 no SSH:

```bash
openssl x509 -in ~/painel-rasp/certs/cert.pem -noout -fingerprint -sha256
```

Compare com a cópia local usando `openssl x509 -in raspberry-cert.pem -noout -fingerprint -sha256`, se tiver OpenSSL instalado. Depois importe o certificado público no armazenamento de confiança do sistema ou navegador que você usa. A interface exata varia por navegador e sistema; inclua apenas o certificado que conferiu. Não distribua a chave privada e não ignore permanentemente erros de certificado.

Para clientes de API, forneça o certificado explicitamente com `--cacert`, sem alterar o armazenamento global. Não use `curl -k` como configuração normal: isso desabilita a verificação de identidade do servidor.

## Consultar com senha

Na própria Raspberry, `curl` solicita a senha sem colocá-la na linha de comando:

```bash
curl --cacert ~/painel-rasp/certs/cert.pem --user admin https://127.0.0.1:8443/status
```

Troque `admin` pelo usuário escolhido. No computador remoto, use o caminho da cópia do certificado e o endereço da placa. HTTPS é obrigatório, mesmo ao consultar a API por senha.

O navegador normalmente guarda as credenciais Basic durante a sessão. Não há botão de logout confiável nesse método. Em computador compartilhado, use um perfil ou janela privada e encerre essa sessão ao terminar. Não inclua senha na URL.

## Consultar com token de API

Envie `Authorization: Bearer TOKEN`. Exemplo Python, executado no computador cliente, pedindo o token de forma oculta e validando o certificado público copiado:

```python
import getpass
import json
import ssl
from urllib.request import Request, urlopen

context = ssl.create_default_context(cafile="raspberry-cert.pem")
token = getpass.getpass("Token de API: ")
request = Request(
    "https://IP_DA_RASPBERRY:8443/api/history?period=24h",
    headers={"Authorization": "Bearer " + token},
)
with urlopen(request, context=context, timeout=10) as response:
    print(json.load(response))
```

O token é aceito nas rotas protegidas e tem acesso de leitura a todos os dados. Não existe token por usuário, expiração automática, escopo por rota ou cadastro remoto. Guardá-lo como hash impede recuperá-lo pelo arquivo; se perder, gere outro.

## Trocar senha e revogar o token

No SSH, como o usuário normal da instalação:

```bash
cd ~/painel-rasp
.venv/bin/python configurar_seguranca.py --reset-auth
sudo systemctl restart painel-rasp
```

Esse comando troca usuário/senha e gera um novo token. Depois do reinício, credenciais anteriores deixam de funcionar e o cache é descartado. Atualize seus clientes. O histórico e os certificados permanecem. Não há recuperação da senha antiga em texto puro.

## Renovar ou trocar o certificado

Antes de expirar, ou se mudar o nome/IP usado:

```bash
cd ~/painel-rasp
.venv/bin/python configurar_seguranca.py --renew-cert
sudo systemctl restart painel-rasp
```

O comando substitui certificado e chave. Copie, confira e estabeleça confiança no novo certificado nos clientes. A renovação não é automática e a reinstalação preserva o certificado existente, mesmo se estiver perto de expirar. Para verificar as datas:

```bash
openssl x509 -in ~/painel-rasp/certs/cert.pem -noout -dates
```

É possível usar um certificado emitido por uma autoridade pública com `--ssl-certfile` e `--ssl-keyfile` no serviço, mas obter e renovar esse certificado, configurar DNS e proteger o acesso externo ficam fora do instalador local. A unidade systemd é recriada pelo instalador; registre essas alterações antes de atualizar.

## Diagnóstico e limites

| Resposta ou sintoma | Ação |
| --- | --- |
| `401` | Forneça usuário/senha ou token válido |
| `429` | Aguarde a janela de 60 segundos após várias tentativas incorretas |
| HTTP simples recusado | Use `https://` na porta 8443 |
| Certificado desconhecido | Confira a impressão digital e configure confiança ou `--cacert` |
| Nome do certificado não corresponde | Use um SAN correto ou gere novo certificado com o endereço desejado |
| Serviço não inicia | Confira credenciais, validade/formato dos arquivos, caminhos de TLS e logs do journal |

O rate limit é local ao processo e baseado no endereço da conexão. Não é uma defesa contra ataques distribuídos; reiniciar também limpa os contadores. Cabeçalhos de proxy não são confiados. Se for adicionar proxy reverso, planeje essa integração explicitamente.

Essa configuração protege a conexão local, mas não transforma a Raspberry em um serviço público gerenciado. Não abra portas no roteador apenas por ter adicionado HTTPS. Para acesso externo, projete também autenticação, atualização do sistema, controle de rede, certificados confiáveis e proteção de disponibilidade.

## Referências

- [FastAPI: HTTP Basic e comparação de credenciais](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/).
- [Uvicorn: configuração de HTTPS](https://www.uvicorn.org/settings/#https).
- [Python: PBKDF2](https://docs.python.org/3/library/hashlib.html#hashlib.pbkdf2_hmac).
