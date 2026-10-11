# Unity Agent

Um agente do Claude Code que fica **sempre de pé no seu PC**, atende pelo
Telegram, e trabalha como porteira: recebe o pedido, decide, despacha para um
executor, e volta com o resultado.

Não é um chatbot. É uma sessão de fundo do Claude Code, dona de um canal do
Telegram, mantida viva por systemd e vigiada por um laço que a recria quando ela
cai.

> **Quer só instalar?** Vá para **[COMECE-AQUI.md](COMECE-AQUI.md)** — são três
> comandos, e o próprio LLM conduz o resto da configuração.

```
Telegram  ──►  plugin telegram (bun server.ts)
                      │  stdio MCP
                      ▼
              sessão de fundo do Claude Code  ── unity-delegar ──►  executor
                      ▲                                            (opencode / nex / sonnet)
                      │  spawn
              unity-daemon.service  ◄── unity-supervisor.timer (2 min) ── unity-ensure
```

## Por que isso existe

O Claude Code sabe rodar uma sessão de fundo (`claude --bg`) e sabe falar com o
Telegram (plugin oficial). O que ele **não** faz é manter isso vivo: o daemon
sai quando o último cliente desconecta, e a sessão morre junto. O canal fica
órfão — o servidor do plugin continua consumindo `getUpdates` e entregando a
ninguém. A mensagem some sem erro.

Este repo é a camada que falta: durabilidade, vigilância e uma persona.

## As quatro peças

| Peça | Arquivo | Papel |
|---|---|---|
| Daemon | `systemd/unity-daemon.service` | Segura o daemon do Claude Code de pé, com `Restart=always`. Sem ele nada sobrevive. |
| Vigia | `systemd/unity-supervisor.timer` + `bin/unity-ensure` | A cada 2 min confere se existe UMA sessão de fundo com UM servidor de canal. Recria se não. |
| Persona | `prompts/*.md` | Como ela fala e como ela decide. Injetado por `--append-system-prompt` no lançamento. |
| Despacho | `bin/unity-despachar` | Manda o trabalho longo para um executor, para o canal não ficar mudo. |

## As faixas de execução

Trabalho longo não é feito na sessão dela — enquanto ela trabalha, o canal fica
mudo. Quem faz é um executor, escolhido por `unity-delegar --nivel`:

| Faixa | Quem é | Quando |
|---|---|---|
| `opencode` | modelo grátis do opencode zen | **padrão.** Tarefa volumosa e já decidida: varrer arquivos aplicando a mesma mudança, escrever teste, traduzir, reformatar, montar página a partir de um modelo |
| `nex` | modelo grátis pela OpenRouter | também custo zero, mais lento porque raciocina mais. Melhor quando a tarefa tem mais de um jeito razoável de ser feita |
| `sonnet` | Claude Sonnet | reserva. Bug de causa desconhecida, decisão de arquitetura, qualquer coisa cujo erro seja caro de desfazer |
| `claude` | Claude Opus | a faixa mais cara. Não é a reserva barata — o nome engana |

As duas primeiras não consomem cota nenhuma. As duas últimas consomem a mesma
cota que mantém a Unity viva, então são exceção, não hábito.

**[MODELOS.md](MODELOS.md)** tem o resto: quais modelos estão de graça hoje,
como listar o catálogo (ele **rotaciona sem aviso**, e modelo que sai não
volta), como trocar o modelo de cada faixa por variável de ambiente, e o que
"grátis" custa em velocidade, limite de uso e privacidade dos dados.

Quando uma faixa grátis termina, **o outro modelo grátis revisa** o que foi
feito e carimba `APROVADO`, `RESSALVAS` ou `PROBLEMAS` no aviso. Revisar custa
zero quando o revisor também é grátis, e "terminou" nunca significou "ficou
bom".

Duas travas aprendidas no caminho: `opencode` e `nex` rodam pelo mesmo binário
e pelo mesmo banco de estado, então **duas delegações simultâneas entre elas**
voltam com "database is locked" — o despachante serializa. E `ok: false` de uma
delegação **não prova que o trabalho falhou**: já aconteceu um site inteiro
funcionando voltar marcado como falha porque o executor deixou um servidor de
teste em primeiro plano e estourou o relógio do shell. Abra e olhe antes de
descartar.

## Decisões que custaram caro (não repita)

**O plugin do Telegram é ligado só no settings da Unity, nunca no global.**
O Telegram aceita **um** consumidor de `getUpdates` por token. Habilitado em
escopo de usuário, toda sessão do Claude Code sobe o próprio `server.ts` e elas
brigam pela fila — quem vence às vezes é uma sessão sem `--channels`, que
consome a mensagem e não tem onde entregar. Sintoma: mensagem sem resposta e
sem erro.

**`defaultMode: dontAsk` não quer dizer "permite tudo".** Quer dizer "não
pergunte", e o que não estiver em `allow` é **negado em silêncio**. Pior: um
veredito `ask` degrada para bloqueio, porque o modo não tem como exibir prompt.
Use `default` + uma lista `allow` explícita.

**Variável de ambiente no lançador não chega na sessão.** `VAR=1 claude --bg`
só define a variável no processo lançador — quem executa a sessão é o daemon do
systemd, cujo ambiente tem `PATH` e mais nada. Config de sessão vai no arquivo
de `--settings`, na chave `env`. Foi isso que fazia toda resposta chegar
duplicada no Telegram: o hook `Stop` não via a variável que devia silenciá-lo.

**O laço precisa de amortecedor.** Uma sessão nova custa ~19 mil tokens só para
nascer. Recriar na primeira falha fazia 10 respawns por dia por causa de
piscadas. `unity-ensure` só age depois de ver a falha **duas vezes seguidas**.

**O agente não pode apagar nada.** `unity-block-delete` nega `rm` e devolve ao
agente a instrução de usar `unity-trash`, que move para `~/.trash-agent/`. Negar
sem alternativa troca paralisia por tarefa pela metade.

**`--permission-mode acceptEdits` não deixa o executor autônomo.** Ele aceita
*edição de arquivo* e nada mais — Bash continua no portão normal, e num
`claude -p` não existe prompt para ninguém responder: a chamada volta com "this
command requires approval". O sintoma engana, porque a lista de comandos
seguros deixa passar leitura: `ls`, `grep`, `git log`, `git status`,
`python3 --version` rodam; `python3 script.py`, `curl`, `getent` e `git commit`
não. Parece sandbox e é permissão. O executor chegou a parar no meio da tarefa
e pedir aprovação no Telegram. Quem conserta é `config/dispatch-settings.json`,
passado com `--settings` em `unity-delegar` — lista `allow` explícita, mesma
doutrina do supervisor. As faixas `gemini` e `opencode` já eram autônomas
(`--dangerously-skip-permissions` e `--auto`); só a do Claude estava meia-aberta.

**No `deny`, `Write(caminho)` é letra morta.** O CLI avisa: regras de caminho só
valem com `Edit(...)`, que cobre toda ferramenta que escreve arquivo. `Write(...)`
no deny não barra nada e dá falsa sensação de barreira.

**Voltar da cota não é o mesmo que continuar.** O árbitro sempre soube detectar
sozinho que a janela de 5 h voltou — mas subia uma sessão *nova*, com contexto
zero, que não sabia que existia trabalho pela metade. Quem tinha de lembrar era
o dono. Agora `unity-ensure` anota o `sessionId` **antes** de derrubar o canal
(depois do `stop` ele some do `agents --json`) e volta com `--resume` mais um
prompt de empurrão — sem o prompt a sessão retomada volta ociosa, esperando
alguém falar, que é exatamente o defeito. A retomada é tentada, nunca exigida:
se o `--resume` falhar, sobe sessão nova, porque canal mudo é pior. Anotação com
mais de 12 h é descartada — aí não é continuar, é ressuscitar.

**No WSL, `enable-linger` não faz a Unity subir com o PC.** O linger mantém o
gerenciador de usuário vivo *enquanto a distro está de pé* — e o Windows não
levanta a distro sozinho, ele espera alguém abrir um terminal. Sintoma: tudo
`enabled`, nada rodando, e a Unity acorda só quando você abre o WSL. Quem
resolve é `windows/unity-autostart.vbs`, na pasta Startup do Windows.

## Custo quando ocioso

Zero token. O vigia roda `claude agents --json`, que fala com o daemon por
socket local — não chama modelo. O que consome é o respawn, e é justamente o que
o amortecedor evita.

## Instalação

Requisitos: Claude Code, Python 3.11+, `bun`, systemd em modo usuário
(`loginctl enable-linger` se for headless), `opencode` para a faixa grátis de
execução, e um bot do Telegram criado no
[@BotFather](https://t.me/BotFather).

### O caminho curto: deixe o LLM configurar

```bash
git clone https://github.com/igorrniemietz/unity-agent.git && cd unity-agent
claude
```

E diga: **"configura a Unity neste PC"**.

O Claude Code lê o [`CLAUDE.md`](CLAUDE.md) deste repo — que é o roteiro de
instalação escrito para um agente, não para humano —, roda o inventário,
instala o que falta, e **pergunta** o que só você sabe: o token do seu bot, o
seu ID de usuário do Telegram, e quais projetos você tem. Ele não chuta nenhum
desses dados, de propósito: token errado não dá erro bonito, dá canal mudo.

### O caminho longo: à mão

```bash
./install.sh
python3 bin/unity-doctor
```

O `install.sh` copia os scripts para `~/.local/bin`, as units para
`~/.config/systemd/user`, reescreve os caminhos para o seu `$HOME`, e liga tudo.
O `unity-doctor` então diz, item por item, o que ainda falta. O que ele vai
cobrar:

1. Ponha o token do bot em `~/.claude/channels/telegram/.env`
2. Copie `config/telegram-access.example.json` para
   `~/.claude/channels/telegram/access.json` e ponha o seu ID de usuário
3. Copie `prompts/projetos.example.md` para `~/.claude/orquestrador/projetos.md`
   e descreva os seus projetos
4. Copie `config/dispatch-settings.json` para `~/.claude/dispatch-settings.json`
   — sem ele o executor despachado trava pedindo aprovação de Bash
5. `systemctl --user start unity-supervisor.service`

O ID numérico do item 2 sai do [@userinfobot](https://t.me/userinfobot) — não é
o `@usuario`, é o número.

### O inventário é a ferramenta de diagnóstico

```bash
python3 bin/unity-doctor        # relatório agrupado por camada
python3 bin/unity-doctor --json # o mesmo, para um agente decidir
```

Classifica em três níveis — **FALTA** (o núcleo não sobe sem isso), **opc**
(recurso extra) e **ok** — e cada item fora do `ok` traz a linha de como
resolver. Nenhum segredo é lido: token e chave são conferidos por existência e
tamanho, nunca pelo conteúdo. Um doctor que imprime chave no terminal é
vazamento com cara de diagnóstico.

### Se o host for Windows (WSL)

Falta um passo: nada no Windows levanta a distro no logon. Copie o lançador
para a pasta Startup do seu usuário do Windows e ajuste o nome da distro
dentro dele, se não for `Ubuntu`:

```bash
cp windows/unity-autostart.vbs \
  "/mnt/c/Users/<seu-usuario>/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/"
```

Ele espera 20s, sobe o WSL escondido e chama o vigia — com até 5 tentativas,
porque uma falha aí deixa a Unity fora do ar até o próximo logon. Para desligar,
apague o arquivo da pasta Startup. Um gatilho no Agendador de Tarefas faria o
mesmo, mas `schtasks /SC ONLOGON` exige elevação; a pasta Startup não.

## O que é opcional

O núcleo é daemon + vigia + persona + despacho. Tudo abaixo liga **um** recurso
e nada mais; sem nenhum deles a Unity atende por texto e trabalha igual.

| Recurso | O que ganha | O que precisa |
|---|---|---|
| Voz — falar | resposta com `.ogg` anexado | `edge-tts` + `ffmpeg` |
| Voz — ouvir | nota de voz transcrita | `whisper-ctranslate2` (usa GPU se houver) |
| Gerar imagem | imagem local, sem API paga | ComfyUI com a API em `:8188` + GPU NVIDIA |
| 2ª faixa grátis | dois executores de custo zero | chave da OpenRouter em `~/.config/unity/openrouter.key` |
| Memória longa | lembrar entre sessões | serviço `ai-memory` em `:49374` (fora deste repo) |
| Rodapé de consumo | gasto por mensagem | roteador de LLM local (fora deste repo) |

A voz padrão é a brasileira **Thalita** (`pt-BR-ThalitaNeural`), monolíngue de
propósito: as multilíngues escapam para o inglês em frase curta. A tabela de
vozes e a de pronúncia estão no topo do `bin/unity-fala`.

O repo **não embute gerador de imagem**. A Unity usa o que estiver de pé na
máquina — o `unity-doctor` checa a porta 8188 porque o caminho mais comum é um
ComfyUI local. O modelo é escolha de quem instala, licença incluída: vários dos
melhores são liberados só para pesquisa, não para trabalho de cliente.

## O que este repo não traz

Tokens, IDs e o índice de projetos — nada disso está aqui. `projetos.md` é o
mapa dos seus repositórios e sai como exemplo. Os scripts leem segredo do
ambiente ou do arquivo de ambiente do canal, nunca embutido.

Também não traz ferramenta pessoal: o que era específico de um dono (radar de
vagas, painel de cliente, controle de gasto doméstico) ficou fora. O que está
aqui é a camada que serve a qualquer um.

## Licença

[MIT](LICENSE). Em português claro: **qualquer pessoa já está autorizada** a
usar, copiar, modificar, distribuir e até vender isto, de graça, sem pedir
permissão a ninguém. Não há chave, cadastro nem licença por pessoa — o arquivo
`LICENSE` no repositório **é** a permissão, e ela vale para todo mundo que
receber uma cópia.

A única obrigação de quem usa é manter o aviso de copyright junto. E a única
coisa que a licença nega é garantia: se quebrar, o problema é de quem rodou.
