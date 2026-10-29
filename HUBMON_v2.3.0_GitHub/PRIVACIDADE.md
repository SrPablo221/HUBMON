# Privacidade

HUBMON não exige conta e não implementa telemetria nem requisições web no código da aplicação. A comunicação DDC/CI é feita localmente com o monitor conectado ao PC.

O aplicativo grava as seguintes informações localmente no perfil do usuário do Windows:

- `%APPDATA%\\HUBMON\\settings.json`: perfis e ajustes salvos.
- `%APPDATA%\\HUBMON\\ps5_library.json`: títulos e observações cadastrados manualmente.

Esses arquivos não são enviados pelo aplicativo. Como podem conter nomes e anotações que o usuário escreveu, não os inclua em relatórios públicos sem revisá-los.

A instalação baixa a dependência `monitorcontrol` do PyPI, de acordo com `requirements.txt`; essa etapa requer conexão com a internet. Essa dependência é externa ao projeto.
