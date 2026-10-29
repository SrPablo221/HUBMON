# HUBMON

**Controle local do monitor para setups com PC e PS5.** O HUBMON usa DDC/CI para trocar a entrada de vídeo e, quando o monitor oferece suporte, ajustar brilho e volume diretamente pelo Windows.

> **Estado do projeto:** versão 2.3.0 — projeto comunitário em desenvolvimento. A troca de entradas e os controles DDC/CI devem ser validados no seu próprio monitor. Não existe executável `.exe` neste lançamento.

## O que ele faz

- Troca a entrada do monitor entre HDMI/PS5 e DisplayPort/PC usando os códigos configurados (`0x01` e `0x03`). Esses códigos funcionaram no monitor usado durante o desenvolvimento; outros modelos podem exigir valores diferentes.
- Detecta monitores acessíveis por DDC/CI e permite selecionar o dispositivo.
- Ajusta brilho via DDC/CI quando o monitor expõe o controle correspondente.
- Envia comandos de volume e mute quando suportados pelo firmware do monitor.
- Salva perfis locais para os modos PS5 e PC.
- Inclui uma biblioteca **manual** de jogos PS5 para cadastrar, pesquisar, editar, favoritar e marcar um jogo como atual.
- Oferece ferramentas de diagnóstico e um log na interface.
- Evita abrir mais de uma instância no Windows para reduzir conflitos de acesso ao barramento DDC/I²C.

## O que ele ainda não faz

- Não detecta automaticamente qual jogo está aberto no PS5.
- Não inicia jogos no console ao clicar em uma capa.
- Não controla o sistema interno do PS5 nem oferece integração com jailbreak.
- Não inclui imagens/capas de jogos automaticamente.

A biblioteca de jogos é apenas um organizador local: marcar um título como “jogo atual” é uma ação manual. A integração local com um console modificado é uma possibilidade futura de pesquisa, não um recurso desta versão.

## Requisitos

- Windows 10 ou Windows 11.
- Python 3.10 ou superior, instalado a partir de [python.org](https://www.python.org/downloads/windows/). Durante a instalação, habilite a opção de adicionar Python ao `PATH`.
- DDC/CI habilitado no menu OSD do monitor.
- Monitor conectado ao PC por cabo compatível com DDC/CI. Alguns adaptadores, docks e KVMs podem bloquear os comandos.
- Conexão com a internet durante a instalação para baixar `monitorcontrol` do PyPI. Depois de instalado, o HUBMON não precisa dos serviços online da Sony e o código do aplicativo não faz requisições web.

## Instalação no Windows

1. Baixe o ZIP do código-fonte pelo GitHub ou extraia o arquivo da versão publicada.
2. Extraia a pasta inteira para um local permanente, por exemplo `Documentos\\HUBMON`.
3. Execute `INSTALAR.bat`. Ele cria um ambiente virtual `.venv` dentro da pasta e instala as dependências sem alterar o Python global.
4. Execute `HUBMON.bat`.
5. Selecione o monitor correto e clique em **Detectar novamente** se ele não aparecer automaticamente.
6. Teste **Modo PS5 · HDMI** e **Modo PC · DisplayPort**.

Os atalhos `HDMI.bat` e `DP.bat` são opcionais; precisam que a instalação anterior tenha sido concluída.

## DDC/CI, brilho, volume e compatibilidade

A comunicação é feita pelo Windows com o monitor através de DDC/CI; não é uma comunicação direta com o PS5. Ative DDC/CI no menu físico do monitor, se houver essa opção.

- O suporte a brilho, volume e mute varia por modelo e firmware.
- A leitura de um valor após enviar um comando não garante, sozinha, que o resultado visível ou audível mudou como esperado.
- A troca de entrada pode não funcionar em monitores que usem outros códigos VCP. Ferramentas avançadas permitem consultar capabilities e enviar um código de entrada manual; faça isso apenas se souber o que está selecionando.
- Evite executar o HUBMON em várias pastas ao mesmo tempo. O bloqueio de instância é implementado para Windows.

## Onde as configurações são guardadas

As configurações e a biblioteca ficam na pasta do usuário do Windows, fora do repositório:

- `%APPDATA%\\HUBMON\\settings.json` — perfis e configurações.
- `%APPDATA%\\HUBMON\\ps5_library.json` — biblioteca local de jogos.

Esses arquivos não são enviados pelo aplicativo. O programa não possui conta, telemetria, login ou integração com serviços online da Sony.

## Testes

Depois de executar `INSTALAR.bat`, execute `TESTAR.bat` ou rode no terminal:

```bat
.venv\\Scripts\\python.exe -m py_compile hub_monitor.py trocar.py
.venv\\Scripts\\python.exe tests\\test_logic.py
```

Os testes usam um monitor simulado e verificam operações da camada DDC/CI. Eles não simulam de forma perfeita o firmware de um monitor e não substituem a validação física do seu equipamento.

## Problemas comuns

**Nenhum monitor aparece**

Confirme que o monitor está ligado, conectado diretamente ao PC quando possível e com DDC/CI ativado no OSD. Tente outro cabo ou porta e clique em Detectar novamente.

**A troca de entrada não funciona**

Os códigos padrão são `0x01` para HDMI/PS5 e `0x03` para DisplayPort/PC porque funcionaram no equipamento de desenvolvimento. Outros monitores podem usar códigos diferentes. Consulte o log e as capabilities do monitor.

**Brilho ou volume não mudam**

O monitor pode não expor o respectivo comando DDC/CI. O controle de volume do monitor também não altera o volume de um headset ligado ao DualSense ou ao PC por outra saída.

**O instalador falha**

Confirme Python 3.10+ e conexão com a internet durante a instalação. Se continuar falhando, abra uma issue e inclua o texto do erro; remova antes qualquer informação pessoal que apareça na captura de tela.

## Contribuições e suporte

Sugestões e relatos de erro são bem-vindos. Leia [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar mudanças e use os modelos de issue para informar o problema ou propor uma função.

## Aviso de marca

HUBMON é um projeto independente e não é afiliado, endossado ou patrocinado pela Sony Interactive Entertainment. “PlayStation” e “PS5” são marcas de seus respectivos titulares. A referência a esses nomes serve apenas para descrever compatibilidade pretendida.

## Licença

Este repositório é distribuído sob a licença MIT. Consulte [LICENSE](LICENSE). A biblioteca `monitorcontrol` é um projeto de terceiros e mantém sua própria licença.
