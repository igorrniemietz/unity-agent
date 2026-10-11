# Comece aqui

Três passos. O resto quem faz é o próprio LLM.

```bash
git clone https://github.com/igorrniemietz/unity-agent.git
cd unity-agent
claude
```

E, na sessão que abrir, diga:

> configura a Unity neste PC

O Claude Code lê o `CLAUDE.md` deste repo, roda o inventário
(`python3 bin/unity-doctor`), instala o que falta, e **pergunta** o que só você
sabe — o token do seu bot do Telegram, o seu ID de usuário, e quais projetos
você tem.

## Antes de começar, tenha em mãos

- **Um bot do Telegram.** Crie em [@BotFather](https://t.me/BotFather) com
  `/newbot`. Guarde o token que ele devolve.
- **O seu ID numérico do Telegram.** Mande qualquer mensagem para
  [@userinfobot](https://t.me/userinfobot) e ele responde o número.

Só isso. Se você não tiver, o agente instala o que dá e deixa esses dois itens
pendentes.

## O que é obrigatório e o que é opcional

Obrigatório: Claude Code, Python 3.11+, `bun`, systemd de usuário, e o
`opencode` (que é a faixa grátis que faz o trabalho longo).

Opcional, e o agente vai te oferecer um por um:

| Recurso | O que você ganha | O que precisa |
|---|---|---|
| Voz — falar | ela responde com áudio anexado | `edge-tts` + `ffmpeg` |
| Voz — ouvir | ela entende sua nota de voz | `whisper-ctranslate2` |
| Gerar imagem | imagem local, sem API paga | ComfyUI + GPU NVIDIA |
| 2ª faixa grátis | dois executores de custo zero | chave da OpenRouter |
| Memória longa | ela lembra entre sessões | serviço `ai-memory` (fora deste repo) |

Nenhum deles é impedimento. Sem todos, a Unity atende por texto e trabalha
normalmente.

## Se algo não funcionar

```bash
python3 bin/unity-doctor
```

Ele diz, item por item, o que está no lugar e o que falta — e como resolver
cada um. É o mesmo arquivo que o agente lê, então pode colar a saída dele na
conversa e pedir ajuda.

## Quer entender como funciona antes de instalar?

Leia o [README](README.md). Ele explica por que a Unity existe, as quatro peças
que a mantêm de pé, e as decisões que custaram caro no caminho.
