# Unity Agent

Um agente do Claude Code que fica **sempre de pé no seu PC**, atende pelo
Telegram, e trabalha como porteira: recebe o pedido, decide, despacha para um
executor, e volta com o resultado.

Não é um chatbot. É uma sessão de fundo do Claude Code, dona de um canal do
Telegram, mantida viva por systemd e vigiada por um laço que a recria quando ela
cai.

```
Telegram  ──►  plugin telegram (bun server.ts)
                      │  stdio MCP
                      ▼
              sessão de fundo do Claude Code  ── unity-despachar ──►  executor
                      ▲                                              (claude / gemini)
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

## Custo quando ocioso

Zero token. O vigia roda `claude agents --json`, que fala com o daemon por
socket local — não chama modelo. O que consome é o respawn, e é justamente o que
o amortecedor evita.

## Instalação

Requisitos: Claude Code, `bun`, systemd em modo usuário (`loginctl enable-linger`
se for headless), e um bot do Telegram criado no [@BotFather](https://t.me/BotFather).

```bash
git clone <este-repo> unity-agent && cd unity-agent
./install.sh
```

O `install.sh` copia os scripts para `~/.local/bin`, as units para
`~/.config/systemd/user`, reescreve os caminhos para o seu `$HOME`, e liga tudo.
Depois disso:

1. Ponha o token do bot em `~/.claude/channels/telegram/.env`
2. Copie `config/telegram-access.example.json` para
   `~/.claude/channels/telegram/access.json` e ponha o seu ID de usuário
3. Copie `prompts/projetos.example.md` para `~/.claude/orquestrador/projetos.md`
   e descreva os seus projetos
4. `systemctl --user start unity-supervisor.service`

## O que este repo não traz

Tokens, IDs e o índice de projetos — nada disso está aqui. `projetos.md` é o
mapa dos seus repositórios e sai como exemplo. Os scripts leem segredo do
ambiente ou do `.env`, nunca embutido.

Alguns scripts (`unity-costs`, `unity-uso`, `unity-alerta-ai-memory`) esperam um
roteador de LLM local e um servidor `ai-memory` que não fazem parte deste repo.
Sem eles a Unity funciona; só o rodapé de consumo fica de fora.
