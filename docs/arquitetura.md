# Arquitetura e interpretação das métricas

## Componentes

O backend usa FastAPI e Uvicorn para HTTP, psutil para a rota original e a biblioteca padrão do Python para o coletor e o SQLite. Um thread coleta métricas do Linux e mantém a leitura mais recente em memória, protegida por um lock. Esse coletor também grava amostras no SQLite. O aplicativo FastAPI atende a interface e as rotas JSON. Seu ciclo de vida inicializa o banco e um único coletor; ao encerrar, sinaliza a parada e aguarda o thread. Use somente um worker, sem múltiplas réplicas compartilhando este banco.

Cada operação no banco abre e fecha sua própria conexão, com timeout de 10 segundos. O banco usa o modo WAL. A interface é HTML, CSS e JavaScript puro, com desenhos em Canvas. Ela não baixa bibliotecas ou fontes externas.

## Origem das métricas

| Campo | Origem | Cálculo e significado |
| --- | --- | --- |
| CPU | Primeira linha de `/proc/stat` | Diferença entre dois contadores agregados; considera idle + iowait como tempo não ocupado |
| RAM | `/proc/meminfo` | `(MemTotal - MemAvailable) / MemTotal × 100` |
| Temperatura | `/sys/class/thermal/thermal_zone0/temp` | Valor dividido por 1.000, em °C; ausente ou inválido gera `null` |
| Disco | `shutil.disk_usage('/')` | Espaço ocupado e total no sistema de arquivos da raiz |
| Tempo ligada | `/proc/uptime` | Primeiro valor, em segundos desde o boot |

CPU é a média agregada de todos os núcleos, na escala de 0 a 100%, e não a soma das porcentagens de cada núcleo. São usados os oito primeiros contadores de `/proc/stat`, evitando contar `guest` novamente. A primeira leitura precisa de uma segunda amostra antes de calcular a utilização.

A definição de RAM aproveita `MemAvailable`: memória usada como cache que o kernel consegue liberar não é automaticamente tratada como indisponível. Os tamanhos detalhados de RAM e disco são expressos em GiB. Na interface atual, ficam no texto de dica dos cartões, acessível ao passar o mouse.

## Coleta e armazenamento

O intervalo normal entre coletas é de aproximadamente 5 segundos. A cada 30 segundos ou mais, o coletor grava **a amostra atual**, não a média de todas as coletas desde a gravação anterior. CPU representa o intervalo entre leituras dos contadores, e RAM/temperatura são valores observados naquela coleta.

Banco: `historico.sqlite3`, na mesma pasta de `painel.py`.

```sql
CREATE TABLE metrics (
    ts INTEGER PRIMARY KEY,
    cpu REAL NOT NULL,
    temp REAL,
    ram REAL NOT NULL
);
```

`ts` é um timestamp Unix em segundos. `cpu` e `ram` são percentuais; `temp` é temperatura em °C ou `NULL`. O relógio do sistema deve estar correto, pois define a posição das leituras no gráfico e a retenção.

Com uma gravação a cada 30 segundos, são aproximadamente 2.880 registros por dia e 86.400 em 30 dias. Isso é uma estimativa de registros, não de tamanho do arquivo. Na primeira gravação e aproximadamente uma vez ao dia, registros com timestamp anterior a 30 dias são removidos. Assim, entre limpezas, o banco pode conter quase um dia adicional. O SQLite pode reutilizar páginas livres sem reduzir o tamanho físico do arquivo.

## Agregação dos gráficos

| Período | Janela de agrupamento |
| --- | --- |
| 1 hora | 30 segundos |
| 24 horas | 3 minutos |
| 7 dias | 20 minutos |
| 30 dias | 90 minutos |

As janelas são alinhadas ao timestamp Unix. Cada ponto usa a média dos valores gravados naquela janela e a média dos timestamps para sua posição horizontal. O campo `samples` informa quantas amostras entraram no ponto. Em temperatura, `AVG` ignora amostras `NULL`.

Essas médias tornam a consulta e a renderização leves, mas podem esconder picos. O último ponto de uma janela ainda em andamento pode mudar quando novas amostras chegam.

O navegador não liga pontos separados por mais que `max(90 segundos, 2 × janela)`. Ausências curtas dentro da mesma janela ou abaixo desse limite podem não aparecer como lacunas. Os gráficos têm escala de 0–100% para CPU/RAM; temperatura começa em 0–80 °C e amplia o limite superior se necessário.

## API HTTPSS

| Rota | Resposta |
| --- | --- |
| `GET /` | Interface HTML |
| `GET /status` | Nova leitura sob demanda, com o contrato original |
| `GET /docs` | Documentação interativa FastAPI |
| `GET /openapi.json` | Esquema OpenAPI |
| `GET /api` | Última amostra em memória |
| `GET /api/history?period=1h` | Histórico agregado; também aceita `24h`, `7d`, `30d` |

Exemplo ilustrativo da leitura atual:

```json
{
  "ts": 1700000000,
  "cpu": 12.5,
  "temp": 57.0,
  "ram": 25.0,
  "ram_used": 0.93,
  "ram_total": 3.71,
  "disk_used": 18.1,
  "disk_total": 28.7,
  "uptime": 3600.0
}
```

O histórico retorna `points`, `start`, `end`, `bucket`, `total_samples` e `first`. Cada ponto tem `ts`, `cpu`, `temp`, `ram` e `samples`. `total_samples` conta todo o banco; `first` é o primeiro timestamp ainda armazenado. Eles não se limitam ao período selecionado. Um histórico vazio tem `points: []` e `first: null`.

Antes da primeira coleta, `/api` responde `503`. Um período inválido responde `422` pela validação do FastAPI; rota inexistente responde `404`; erro interno responde `500`. As respostas têm `Cache-Control: no-store`. Arquivos arbitrários e o banco não são servidos por HTTP.

## Comportamento em falhas

Erros de coleta ou gravação são registrados no journal; o coletor tenta novamente. A API pode continuar devolvendo a última leitura em memória. A interface marca uma leitura com mais de 20 segundos como atrasada.

Se o processo encerrar com falha, systemd tenta reiniciá-lo após 5 segundos, sujeito aos limites de reinício do próprio systemd. Um `systemctl stop` intencional não provoca reinício automático. Não há fila de amostras não gravadas, preenchimento de intervalos perdidos ou exportação automática.

## Compatibilidade com a API original

`GET /status` continua coletando no momento da requisição, usando psutil, e preserva estes campos:

| Campo | Significado original preservado |
| --- | --- |
| `cpu_usage` | `psutil.cpu_percent(interval=1)`; cada chamada leva aproximadamente 1 segundo |
| `memory.total` | RAM total em GiB, arredondada para duas casas |
| `memory.used` | RAM usada informada pelo psutil, em GiB |
| `memory.free` | RAM **disponível** (`available`), em GiB, apesar do nome histórico `free` |
| `memory.percent` | Percentual de uso do psutil |
| `disk.total`, `disk.used`, `disk.free` | Tamanhos do sistema de arquivos `/`, em GiB |
| `temperature` | Primeiro sensor `cpu_thermal`, em °C, ou string `N/A` |
| `power` | String `Battery` se existe `/sys/class/power_supply/BAT0`, senão `Plugged In` |
| `os` | `platform.system()` |
| `os_version` | `platform.release()` (versão do kernel) |

Esses campos não são renomeados para os campos de `/api`. A RAM usada do psutil não precisa ser igual a `MemTotal - MemAvailable`; por isso os valores absolutos das duas rotas podem diferir. A temperatura de `/status` depende da chave do sensor que a API antiga utilizava e pode mostrar `N/A` mesmo quando o dashboard lê a zona térmica diretamente. O campo `power` é apenas a heurística original, não uma medição de tensão ou de qualidade da fonte.

Consultar `/status` não grava uma amostra extra no histórico nem interrompe o coletor. As rotas síncronas são atendidas pelo pool de threads do FastAPI. `/api` consulta o último valor em memória; `/api/history` consulta SQLite. Os horários das leituras podem diferir entre as rotas.

O serviço e as execuções manuais agora usam HTTPS em 8443. Existe apenas uma aplicação: todas as rotas usam a porta escolhida para aquele processo. Clientes antigos em HTTP nas portas 8000 ou 8080 precisam migrar para HTTPS e fornecer credenciais. Não execute uma cópia antiga sem proteção para contornar essa mudança.

O HTML do dashboard não precisa de internet após instalar. A interface interativa padrão do FastAPI em `/docs` pode carregar assets de CDN; o JSON de `/openapi.json` permanece local.

## Autenticação e transporte

O ciclo de vida carrega `auth.json` antes do banco e do coletor. Arquivo ausente ou inválido impede a inicialização. O Uvicorn recebe certificado e chave explicitamente e desativa confiança em cabeçalhos de proxy; o middleware recusa requisições cujo esquema não seja HTTPS. Não há rota pública de métricas, docs ou esquema OpenAPI.

HTTP Basic atende o navegador e Bearer atende as integrações. A senha usa PBKDF2-HMAC-SHA256, salt aleatório de 16 bytes e 600.000 iterações. O token é aleatório, de alta entropia, e seu hash SHA-256 é armazenado. Comparações de hashes usam `hmac.compare_digest`.

Para não recalcular PBKDF2 em cada polling, credenciais verificadas ficam em um cache de no máximo 32 identificadores HMAC, com chave efêmera do processo, durante 60 segundos. Não há senha em texto puro nesse cache. Mudar `auth.json` exige reiniciar o serviço para invalidar a configuração carregada e o cache.

Cinco tentativas inválidas com cabeçalho de autenticação por endereço de origem em 60 segundos bloqueiam novas tentativas daquele endereço até o fim da janela (`429`, `Retry-After: 60`). Requisições sem credenciais retornam `401`; HTTP simples retorna `400`. O controle é local ao processo, limitado a 512 endereços, e pode admitir tentativas concorrentes antes de registrar os resultados. Não é uma proteção distribuída contra força bruta.

O esquema OpenAPI declara Basic e Bearer como alternativas. Todas as respostas incluem `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Referrer-Policy: no-referrer`.
