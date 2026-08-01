# Para onde despachar

Índice dos projetos que a Unity conhece. Ela usa isto para transformar um
apelido ("o kanban", "o site") no caminho real antes de despachar.

Sem este arquivo ela ainda funciona — mas passa a perguntar o caminho a cada
pedido, o que na prática trava o despacho.

## Projetos

- **exemplo-app** — `/home/voce/projetos/exemplo-app`
  App em Next.js. Apelidos: "o app", "o site".
  Executor preferido: claude.

- **exemplo-scripts** — `/home/voce/projetos/exemplo-scripts`
  Automações em Python. Apelidos: "os scripts".
  Executor preferido: gemini (tarefa mecânica, barata).

## Onde mora a infra

- Scripts da Unity: `~/.local/bin/unity-*`
- Units do systemd: `~/.config/systemd/user/unity-*`
- Log do vigia: `~/.local/share/unity-supervisor/ensure.log`
- Fila de despachos: `~/.local/share/unity-orquestrador/despachos.jsonl`
