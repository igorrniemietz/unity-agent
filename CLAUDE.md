# Instruções para o agente que vai instalar a Unity

Você está num clone do `unity-agent`. Alguém abriu o Claude Code aqui e pediu
para você **configurar a Unity neste PC**. Este arquivo é o roteiro dessa
conversa. Siga-o de cima para baixo.

A Unity é um agente do Claude Code que fica sempre de pé, atende pelo Telegram e
despacha trabalho longo para executores. O `install.sh` resolve a parte
mecânica. O que ele **não** resolve é tudo que depende de um dado que só o dono
da máquina tem — e é aí que você entra.

## A regra que vale mais que todas

**Nunca invente um dado que é do dono.** Token de bot, ID de usuário do
Telegram, chave de API, nome dos projetos dele: isso você PERGUNTA, uma coisa
por vez, e espera a resposta. Um token chutado não dá erro bonito — ele dá
canal mudo, que é o sintoma mais difícil de diagnosticar neste sistema.

Se ele não tiver o dado em mãos, instale o que der, deixe o item pendente, e
diga em uma linha o que falta e onde ele põe quando tiver.

## Passo 0 — entenda o terreno antes de tocar em nada

```bash
python3 bin/unity-doctor
```

Esse é o inventário. Ele classifica cada item em três níveis, e a diferença
manda no seu plano:

- **FALTA** — o núcleo não funciona sem isso. Resolva.
- **opc** — recurso extra. A Unity sobe sem. Só ofereça; não empurre.
- **ok** — já está lá. Não mexa.

Cada item que não está `ok` já vem com a linha `→` dizendo como resolver.
Quando a linha disser "PERGUNTE ao dono", é literal: aquele dado não existe em
lugar nenhum da máquina.

Rode `unity-doctor --json` se preferir decidir a partir do JSON.

## Passo 1 — o que precisa estar no PC antes

Confira pelo doctor e instale só o que faltar. Em ordem de importância:

| O que | Por que | Como |
|---|---|---|
| Claude Code | é o motor; a Unity é uma sessão dele | já está instalado se você está rodando |
| Python 3.11+ | os scripts usam sintaxe nova | gerenciador de pacotes do sistema |
| `bun` | roda o servidor do canal do Telegram | `curl -fsSL https://bun.sh/install \| bash` |
| systemd de usuário | mantém tudo de pé | em host headless: `loginctl enable-linger $USER` |
| `opencode` | a faixa grátis que faz o trabalho longo | `curl -fsSL https://opencode.ai/install \| bash` |

Depois do `opencode` instalado, ele ainda precisa de login no provedor:
`opencode auth login`. Isso abre um fluxo interativo — **não tente fazer por
ele**. Peça que ele rode no terminal e diga quando terminar.

Com o login feito, **confira que o modelo padrão ainda existe**:

```bash
opencode models | grep mimo
```

O catálogo gratuito rotaciona sem aviso, e modelo que sai não volta. Se não
aparecer, escolha outro da lista e diga a ele qual você escolheu e por quê —
`MODELOS.md` tem a tabela e a variável de ambiente que troca
(`UNITY_OPENCODE_MODEL`). Não deixe isso para depois: o sintoma de modelo
inexistente é a delegação morrer em poucos segundos com "Unexpected server
error", que parece queda do provedor e não é.

## Passo 2 — rode o instalador

```bash
./install.sh
```

Ele é idempotente: rodar de novo sobrescreve os scripts e recarrega o systemd,
mas não duplica nada e **preserva** o que já estiver configurado
(`access.json`, o arquivo de ambiente do canal e `projetos.md`).

O que ele faz: copia `bin/` para `~/.local/bin`, as units para
`~/.config/systemd/user`, os prompts para `~/.claude/orquestrador`, reescreve
todo caminho `/home/reaper` para o `$HOME` de quem instala, aponta a unit do
daemon para o `claude` real, e liga daemon + timers.

Se `~/.local/bin` não estiver no `PATH` dele, avise — vários scripts chamam uns
aos outros pelo nome.

## Passo 3 — o canal do Telegram (aqui você conversa)

Três dados, nesta ordem. Pergunte um, espere, siga.

**1. O bot.** Pergunte se ele já tem um bot do Telegram. Se não tiver, mande
criar no [@BotFather](https://t.me/BotFather) — é `/newbot`, dois nomes, e sai
um token. Peça o token.

Grave em `~/.claude/channels/telegram/.env`, na forma
`TELEGRAM_BOT_TOKEN=<o token>`, e deixe o arquivo em `chmod 600`.

> **Um token = um consumidor.** O Telegram entrega `getUpdates` para UM
> processo só. Se ele já usa esse bot em outro lugar, as duas pontas vão brigar
> pela fila e a mensagem vai sumir sem erro. Nesse caso: bot novo.

**2. O ID dele.** Não é o `@usuario`, é o número. Ele descobre mandando
qualquer coisa para [@userinfobot](https://t.me/userinfobot). Peça o número e
ponha em `~/.claude/channels/telegram/access.json`, no formato do
`config/telegram-access.example.json`.

Esse arquivo é a allowlist: quem não está nele não fala com a Unity. Enquanto
estiver com o ID de exemplo, o canal responde a ninguém — o doctor marca isso
como FALTA de propósito.

**3. Teste.** Com daemon de pé e canal armado, peça que ele mande "oi" para o
bot. Se o 👀 aparecer na mensagem dele, o canal está vivo. Se não aparecer em
uns 30s, veja `~/.claude/daemon.log` e
`systemctl --user status unity-daemon.service`.

## Passo 4 — a persona e o índice de projetos

Três arquivos em `~/.claude/orquestrador/`. O `install.sh` já põe dois:

- `persona.md` — como ela fala (texto puro, linha curta, português, resposta de
  1 a 3 linhas). **Não reescreva isso por conta própria.** Tudo ali é resultado
  de erro medido; mexer sem motivo quebra o tom.
- `roteamento.md` — como ela decide entre responder, delegar e para qual faixa.
  Mesma regra.
- `projetos.md` — **este é dele e só ele sabe.** É a lista de destinos: o que
  cada projeto é, onde fica, e por quais apelidos ele chama cada um.

Sobre o `projetos.md`: o `install.sh` cria a partir do exemplo. Pergunte quais
projetos ele tem e preencha junto com ele. Não precisa ser completo no primeiro
dia — mas um `projetos.md` vazio faz a Unity perguntar "qual projeto?" em toda
mensagem, e é a reclamação número um de quem instala e não preenche.

Se ele não quiser detalhar agora, deixe o exemplo e diga: "quando você for
pedir trabalho num projeto, me fala o caminho uma vez e eu anoto aqui".

## Passo 5 — ofereça os opcionais, um por um

Estes NÃO fazem parte do núcleo. Cada um liga um recurso e nada mais. Pergunte
se ele quer, explique o que ganha, e siga sem se a resposta for não.

### Voz — ela responder falando e entender nota de voz

Duas metades independentes:

- **Falar** (`unity-fala`): `pip install edge-tts` + `ffmpeg` no sistema.
  Gera um `.ogg` que a Unity anexa na resposta. Roda offline depois de
  instalado, custo zero.
- **Ouvir** (`unity-transcreve`): `pip install whisper-ctranslate2`. Transcreve
  a nota de voz que ele mandar. Usa GPU se houver; na CPU fica lento mas
  funciona.

A voz padrão do repo é a brasileira **Thalita** (`pt-BR-ThalitaNeural`),
monolíngue — escolhida porque as multilíngues escapam para o inglês em frase
curta. Para trocar, veja a tabela no topo do `bin/unity-fala`.

Pergunte se ele quer que a voz seja **padrão** (todo conteúdo sai com áudio
anexado) ou **sob pedido**. Padrão é o comportamento do repo; se ele preferir
sob pedido, ajuste a seção de voz no `persona.md` dele e diga que ajustou.

Sem nada disso instalado, a Unity responde só por texto e todo o resto funciona
igual.

### Gerador de imagem

O repo **não embute nenhum**. A Unity usa o que estiver de pé na máquina, e o
doctor checa a porta 8188 porque o caminho mais comum é um **ComfyUI local**
com a API ligada.

Isso é a cara da máquina dele, não do repo: precisa de GPU com VRAM suficiente,
dos modelos baixados (vários GB) e de atenção à licença de cada modelo — alguns
dos melhores são só para pesquisa, não para trabalho de cliente.

Ofereça assim: "dá para ligar geração de imagem local se você tiver GPU
NVIDIA — é instalar o ComfyUI e subir com a API na 8188. Quer que eu te guie
nisso agora ou deixa para depois?" Se ele não tiver GPU, diga direto que não
vale a pena e siga.

Sem gerador, a Unity simplesmente não gera imagem. Nenhum outro recurso é
afetado.

### Segunda faixa grátis (OpenRouter)

Uma chave em `openrouter.ai`, gravada em `~/.config/unity/openrouter.key`.
Serve para ter dois executores de custo zero em vez de um — útil porque o
revisor cruzado usa o modelo da outra faixa. Opcional; sem a chave,
`--nivel nex` não roda e o `--nivel opencode` cobre tudo.

Se ele ligar esta faixa, confirme que o modelo padrão ainda é gratuito:

```bash
curl -s https://openrouter.ai/api/v1/models \
  | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data'] if m['id'].endswith(':free')]"
```

Isso já pegou de verdade: em 11/10/2026 a variante `:free` do modelo que dava
nome à faixa tinha saído do catálogo, enquanto a versão **paga** de mesmo nome
continuava lá. O nome existia e a faixa grátis não — e o erro não dizia isso.
`MODELOS.md` tem a tabela de alternativas e a variável `UNITY_NEX_MODEL`.

### Serviços externos (memória e rodapé de consumo)

`ai-memory` (porta 49374) e um roteador de LLM local (porta 8787) **não fazem
parte deste repo**. Sem eles:

- a Unity lembra só do que está nos prompts e no histórico de sessão;
- o rodapé de consumo fica incompleto.

Nada mais muda. Não tente instalar nenhum dos dois sem ele pedir.

## Passo 6 — se o host for Windows (WSL)

Pegadinha que deixa tudo `enabled` e nada rodando: **no WSL o
`enable-linger` não sobe a distro no logon.** O Windows espera alguém abrir um
terminal. Resultado: a Unity só acorda quando ele abre o WSL.

```bash
cp windows/unity-autostart.vbs \
  "/mnt/c/Users/<usuario-windows>/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/"
```

Pergunte o nome do usuário do Windows e o nome da distro (o `.vbs` assume
`Ubuntu`; ajuste dentro do arquivo se for outra). Para desligar depois, é só
apagar o arquivo.

## Passo 7 — feche verificando, não anunciando

```bash
python3 bin/unity-doctor
```

Nada de "instalei, deve estar funcionando". O fechamento é:

1. doctor sem nenhum FALTA;
2. `systemctl --user status unity-daemon.service` ativo;
3. ele mandou uma mensagem no bot e recebeu resposta.

Se o item 3 não acontecer, o lugar para olhar é `~/.claude/daemon.log` e
`claude agents --json` (que deve mostrar uma sessão de fundo com um canal).

Então entregue um resumo curto: o que ficou ligado, o que ficou de fora por
escolha dele, e o que ficou pendente esperando um dado.

## Armadilhas que já custaram caro — não descubra de novo

**Plugin do Telegram só no settings da Unity, nunca no global.** Habilitado em
escopo de usuário, toda sessão do Claude Code sobe o próprio servidor de canal
e elas brigam pela fila do `getUpdates`. Quem vence às vezes é uma sessão sem
canal, que consome a mensagem e não tem onde entregar. Sintoma: mensagem sem
resposta e sem erro.

**`defaultMode: dontAsk` não quer dizer "permite tudo".** Quer dizer "não
pergunte" — e o que não estiver em `allow` é negado em silêncio. Pior: um
veredito `ask` degrada para bloqueio, porque o modo não tem como mostrar
prompt. Use `default` com lista `allow` explícita, que é o que
`config/unity-settings.json` já faz.

**Variável de ambiente no lançador não chega na sessão.** `VAR=1 claude --bg`
define a variável no processo lançador; quem executa a sessão é o systemd, cujo
ambiente tem `PATH` e pouco mais. Config de sessão vai na chave `env` do
arquivo de `--settings`.

**Sem `dispatch-settings.json`, o executor despachado trava.**
`--permission-mode acceptEdits` aceita edição de arquivo e nada mais; num
`claude -p` não existe ninguém para responder a um pedido de aprovação de Bash.
O sintoma engana porque leitura passa (`ls`, `grep`, `git log`) e execução não.

**No `deny`, `Write(caminho)` é letra morta.** Regra de caminho só vale com
`Edit(...)`, que cobre toda ferramenta que escreve arquivo.

**O agente não apaga nada.** `unity-block-delete` nega `rm` e manda usar
`unity-trash`, que move para `~/.trash-agent/`. Não "conserte" isso removendo o
hook: negar sem oferecer alternativa troca paralisia por tarefa pela metade.

## O que você NÃO deve fazer aqui

- Não comite nada neste clone sem ele pedir. É a máquina dele, não um PR.
- Não leia nem imprima o conteúdo de token, chave ou `access.json`. O doctor
  confere por existência e tamanho de propósito.
- Não suba `ai-memory`, roteador, ComfyUI nem nada pesado por iniciativa
  própria.
- Não reescreva `persona.md` e `roteamento.md` para "melhorar". Cada regra ali
  é cicatriz de um erro medido.
- Não prometa que algo funcionou antes de ver funcionando.
