# Como contribuir

Obrigado por ajudar a melhorar o HUBMON.

## Antes de abrir uma issue

- Verifique se a versão e o ambiente (Windows, Python e modelo do monitor) estão informados.
- Para erros DDC/CI, informe conexão de vídeo (HDMI/DisplayPort), se DDC/CI está habilitado e o texto relevante do log.
- Não publique dados pessoais, identificadores da conta, arquivos de configuração privados ou imagens com notificações pessoais.
- Não diga que um recurso está confirmado no seu monitor sem ter feito o teste físico.

## Alterações de código

1. Faça uma cópia ou fork do repositório.
2. Mantenha a interface e as mensagens em português brasileiro.
3. Evite adicionar dependências quando a biblioteca padrão resolver o problema.
4. Preserve a execução de DDC/CI fora da thread da interface.
5. Execute `python -m py_compile hub_monitor.py trocar.py` e `python tests/test_logic.py`.
6. Descreva claramente o que você testou em hardware real e o que foi testado apenas por simulação.

## Escopo

A prioridade do projeto é controle local de monitor. A biblioteca PS5 desta versão é manual; não envie PRs que apresentem a detecção ou a inicialização direta de jogos como algo já funcional sem uma integração real testada e documentada.
