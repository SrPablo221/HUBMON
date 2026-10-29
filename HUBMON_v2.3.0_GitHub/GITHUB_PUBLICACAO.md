# Guia de publicação do HUBMON no GitHub (Windows)

Este arquivo é um guia para o mantenedor; não é necessário para usuários comuns.

## Caminho recomendado: GitHub Desktop

1. Crie uma conta em `https://github.com/`, se ainda não tiver uma.
2. Instale o GitHub Desktop em `https://desktop.github.com/` e entre na sua conta.
3. Extraia o pacote `HUBMON_v2.3.0_GitHub.zip` para uma pasta permanente, por exemplo `Documentos\\HUBMON`.
4. No GitHub Desktop, use **File > Add local repository** e selecione essa pasta. Se ela ainda não for um repositório Git, escolha a opção para criar um repositório no local selecionado.
5. Confirme que o nome do repositório local é `HUBMON` e que o branch inicial é `main`.
6. Revise a lista de arquivos alterados. O `.gitignore` exclui `.venv`, caches e arquivos locais típicos. Não adicione logs ou dados pessoais.
7. Faça o primeiro commit com uma mensagem como `Prepare HUBMON 2.3.0 public release`.
8. Clique em **Publish repository**. Escolha `HUBMON` como nome, escreva uma descrição, marque **Public** e publique.
9. Abra o repositório no navegador e revise o README, os arquivos e a licença.

## Ajustes recomendados no repositório

- Descrição: `Controle local de monitor via DDC/CI para setups com PC e PS5.`
- Tópicos: `windows`, `python`, `ddc-ci`, `monitor-control`, `tkinter`, `playstation-5`.
- Confirme se o repositório deve ser público antes de publicar. O conteúdo que for publicado pode ser copiado por outras pessoas.
- A licença MIT permite redistribuição e alterações; mantenha-a somente se você tem o direito de publicar o código sob essa licença.

## Criar uma versão (Release)

1. Abra o repositório no GitHub e clique em **Releases > Draft a new release**.
2. Crie a tag `v2.3.0` e título `HUBMON 2.3.0`.
3. No texto da release, copie o resumo de `CHANGELOG.md` e explique que não há `.exe` nesta versão.
4. Anexe um ZIP de usuário contendo os arquivos da aplicação, scripts `.bat`, `requirements.txt` e instruções. Não inclua `.venv`, caches, arquivos de configuração pessoais ou biblioteca pessoal de jogos.
5. Publique somente depois de testar a instalação e o comportamento no Windows real.

## Alternativa pelo site do GitHub

É possível criar um repositório vazio no site e usar **Add file > Upload files**, mas é fácil deixar de fora arquivos ocultos como `.gitignore` e `.github`. Para preservar toda a estrutura de pastas e o workflow de testes, recomendamos GitHub Desktop.

## Checklist antes da publicação

- [ ] Confirmar titularidade/autorização para publicar todo o código incluído.
- [ ] Validar que o repositório não contém senhas, tokens, arquivos pessoais ou dados do usuário.
- [ ] Rodar os testes (`TESTAR.bat`) em Windows.
- [ ] Testar troca HDMI/DisplayPort e brilho no monitor real.
- [ ] Verificar instalação limpa em uma pasta nova e com Python 3.10+.
- [ ] Confirmar que README e limitações estão corretos.
- [ ] Só então anunciar a versão no YouTube.
