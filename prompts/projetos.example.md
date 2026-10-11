# Para onde despachar

Índice dos projetos que a Unity conhece. Ela usa isto para transformar um
apelido ("o kanban", "o site") no caminho real antes de despachar.

Sem este arquivo ela ainda funciona — mas passa a perguntar "qual projeto?" a
cada pedido, o que na prática trava o despacho. É a reclamação número um de
quem instala e não preenche.

**Copie para `~/.claude/orquestrador/projetos.md` e troque pelos seus.** Este
arquivo é o único do repo que é inteiramente seu; ele nunca é versionado.

## Como a Unity usa isto

Ela casa o seu pedido contra a lista e produz **um de três resultados**, nunca
dois:

1. **Casamento único** → age, e declara o destino na primeira linha da
   resposta. Se ela errou o alvo, você vê em segundos em vez de descobrir
   depois do commit.
2. **Ambíguo** (dois candidatos plausíveis) → pergunta qual, listando os
   candidatos. Ela não escolhe "o mais próximo": trabalhar no projeto errado em
   silêncio é o pior resultado possível.
3. **Nenhum** → pergunta se é para começar do zero, e acrescenta a linha aqui
   quando você confirma. É assim que a lista se mantém viva.

Por isso vale anotar os **apelidos** com que você realmente fala. "o site" é
mais útil aqui que o nome formal do repositório.

## Projetos

- **exemplo-app** — `/home/voce/projetos/exemplo-app`
  App em Next.js, loja de um cliente. Apelidos: "o app", "o site", "a loja".
  Executor preferido: `sonnet` (mexe em código de produção, erro é caro).

- **exemplo-scripts** — `/home/voce/projetos/exemplo-scripts`
  Automações em Python, uso interno. Apelidos: "os scripts", "as automações".
  Executor preferido: `opencode` (tarefa mecânica, custo zero).

- **exemplo-site-estatico** — `/home/voce/projetos/exemplo-site-estatico`
  HTML e CSS à mão. Apelidos: "a landing", "a página".
  Executor preferido: `nex` (trabalho aberto, custo zero, não é urgente).

### Armadilhas que vale anotar junto

Se um projeto seu tem alguma dessas, escreva **aqui**, na linha dele — é o
único lugar onde a Unity vai olhar antes de agir:

- **Duas pastas parecidas, só uma ativa.** Diga qual é a ativa e que a outra é
  a antiga. Nome parecido é a causa mais comum de trabalho no lugar errado.
- **Deploy com regra própria.** Autor de commit exigido, publicação por `rsync`
  em vez de `git`, pasta separada sem `git` só para publicar.
- **Nome com espaço.** Escreva que vai entre aspas no shell.
- **Diretório guarda-chuva.** Se uma pasta contém vários projetos, diga que ela
  nunca deve ser tratada como um projeto só.

## Onde mora a infra

- Scripts da Unity: `~/.local/bin/unity-*`
- Units do systemd: `~/.config/systemd/user/unity-*`
- Prompts (persona, roteamento, este arquivo): `~/.claude/orquestrador/`
- Log do vigia: `~/.local/share/unity-supervisor/ensure.log`
- Fila de despachos: `~/.local/share/unity-orquestrador/despachos.jsonl`
- Inventário do que falta: `unity-doctor`
