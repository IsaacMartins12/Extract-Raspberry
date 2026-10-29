# Desenvolvimento e publicação no GitHub

Repositório existente: [IsaacMartins12/Extract-Raspberry](https://github.com/IsaacMartins12/Extract-Raspberry).

Esta atualização foi preparada em uma branch derivada do repositório original, preservando seu histórico, a licença MIT e a rota `/status`. Não é necessário criar um repositório novo ou substituir a branch principal à força.

## Clonar e preparar o ambiente

No PowerShell do Windows, para desenvolvimento e testes:

```powershell
git clone https://github.com/IsaacMartins12/Extract-Raspberry.git
cd Extract-Raspberry
git switch -c minha-alteracao
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements/dev.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

O monitor real depende do Linux; os testes podem usar banco temporário e leituras simuladas no Windows. Não execute o coletor como um monitor do Windows.

## Revisar e publicar alterações

```powershell
git status --short
git diff
git add extract_raspberry scripts requirements README.md docs tests .gitignore .gitattributes
git diff --cached --stat
git commit -m "Adiciona autenticacao e HTTPS ao monitor"
git push -u origin HEAD
```

Configure `git config user.name` e `git config user.email` com seus dados se o Git solicitar identidade. Use a autenticação oferecida pelo Git no seu computador. Não coloque tokens na URL ou nos arquivos. O GitHub não aceita a senha da conta para autenticar operações Git HTTPS.

Após o push, abra um pull request comparando sua branch com `main`, confira o diff e os testes e integre quando estiver pronto. Um push no GitHub não instala o programa na Raspberry.

O `.gitignore` exclui o histórico SQLite, WAL/SHM, backups, ambiente virtual, caches, arquivos `.env`, `mode.json`, `auth.json`, certificados e chaves privadas. Ele não remove arquivos já rastreados. Não é necessário copiar o histórico da placa para publicar o projeto. Preserve `LICENSE` e o aviso de copyright existente.

## Atualizar a Raspberry depois da integração

No clone da Raspberry:

```bash
cd ~/src/monitor-rasp
git pull --ff-only
sh scripts/instalar.sh
```

Antes da integração em `main`, para testar a branch desta atualização:

```bash
git fetch origin
git switch --track origin/reorganiza-estrutura
sh scripts/instalar.sh
```

Se a branch já existir localmente, use `git switch reorganiza-estrutura` e `git pull --ff-only`. Não force a troca se houver alterações locais; revise-as primeiro. Consulte o README para requisitos do ambiente virtual e o guia de operação para preservar e copiar o banco.

## Referências

- [Gerenciar repositórios remotos](https://docs.github.com/en/get-started/git-basics/managing-remote-repositories).
- [Publicar código local](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
