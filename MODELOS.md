# Quais LLM usar, e quais saem de graça

A Unity não é um modelo. Ela é uma sessão do Claude Code que **decide** e
**delega** — e quem faz o trabalho longo é um executor, que pode ser um modelo
de graça. Este arquivo é sobre essa escolha: o que existe, o que custa zero, e
qual serve para quê.

Vale a pena ler antes de instalar, porque a escolha do executor é a diferença
entre uma Unity que trabalha o dia inteiro sem cobrar nada e uma que queima sua
cota em três tarefas.

## Em cinco linhas

- A Unity em si roda no **Claude** (é uma sessão do Claude Code; não tem como
  ser outra coisa).
- O **trabalho longo** vai para um executor, e há **duas faixas de custo zero**.
- Faixa grátis padrão: **`opencode`** — modelo do opencode zen, hoje o
  **MiMo v2.6 Flash**.
- Segunda faixa grátis: **`nex`** — um modelo `:free` da **OpenRouter**.
- As faixas pagas (`sonnet`, `claude`) consomem a mesma cota que mantém a Unity
  viva. São exceção, não hábito.

## As faixas, e quando usar cada uma

| Faixa | Custo | Use quando |
|---|---|---|
| `opencode` | **zero** | padrão. Tarefa volumosa e **já decidida**: varrer arquivos aplicando a mesma mudança, escrever teste para código existente, traduzir, renomear, reformatar, montar página a partir de um modelo, ler log grande e extrair o que importa |
| `nex` | **zero** | mesma coisa, mas quando a tarefa é **mais aberta** — há mais de um jeito razoável de fazer. Mais lenta, porque raciocina mais antes de escrever |
| `sonnet` | cota do Claude | bug de **causa desconhecida**, decisão de arquitetura, qualquer coisa cujo erro seja caro de desfazer |
| `claude` | cota do Claude, **a mais cara** | é **Opus**. O nome engana: não é a reserva barata, é a faixa mais cara de todas. Já custou dinheiro por confusão com `sonnet` |

A regra que resolve 90% dos casos: **volumoso e já decidido vai para as faixas
grátis, sempre.** O gatilho não é a tarefa ser fácil — é ela ser grande e não
exigir julgamento. O que fica fora: decisão de arquitetura, bug de causa
desconhecida, e erro caro de desfazer.

```bash
unity-delegar --nivel opencode --projeto meu-app \
  --dir ~/projetos/meu-app \
  "add tests for the parser module"
```

## O catálogo rotaciona — e isso é a armadilha principal

Modelo grátis **sai de catálogo sem aviso**, e quando sai não volta. O sintoma
não é uma mensagem clara: a delegação morre em poucos segundos com algo como
"Unexpected server error", ou simplesmente não produz nada. É fácil
diagnosticar como queda do provedor quando é só o nome do modelo que não existe
mais.

Antes de culpar qualquer outra coisa, liste o catálogo:

```bash
# o que o opencode zen tem AGORA
opencode models

# o que a OpenRouter tem de graça AGORA
curl -s https://openrouter.ai/api/v1/models \
  | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data'] if m['id'].endswith(':free')]"
```

Se o modelo que a Unity usa não aparecer na lista, o conserto é apontar para
outro — não redelegar igual.

### Isto já aconteceu de verdade

Medido em **11/10/2026**: o padrão da faixa `nex` era
`nex-agi/nex-n2.5-pro:free`, e a variante gratuita **tinha saído do catálogo**.
O modelo pago com o mesmo nome continuava lá, a US$ 0,075 por milhão de tokens
de entrada — ou seja, barato, mas não zero. Quem instalasse herdaria uma faixa
que falha. Por isso o padrão de hoje é outro, e por isso este arquivo existe.

O mesmo já tinha acontecido na faixa `opencode`: o DeepSeek saiu do catálogo
zen e o rótulo continuou dizendo "DeepSeek (opencode)" por duas semanas,
descrevendo um modelo que não estava mais sendo usado.

## Como trocar o modelo de uma faixa

Duas variáveis de ambiente, sem mexer em código:

```bash
# faixa opencode
export UNITY_OPENCODE_MODEL="opencode/mimo-v2.6-flash-free"

# faixa nex (qualquer modelo da OpenRouter, com o prefixo openrouter/)
export UNITY_NEX_MODEL="openrouter/poolside/laguna-s-2.1:free"
```

Para valer sempre, ponha no seu `~/.bashrc` — ou, melhor, na chave `env` do
`~/.claude/supervisor-settings.json`, porque **variável definida no lançador não
chega na sessão**: quem executa a Unity é o systemd, cujo ambiente tem `PATH` e
pouco mais.

## O que existe de graça hoje

Listado em **11/10/2026**. Confira com os comandos acima antes de confiar —
esta lista envelhece por desenho.

### opencode zen (faixa `opencode`)

11 modelos no catálogo, dos quais 10 marcados `-free`. Entre eles:

- `opencode/mimo-v2.6-flash-free` — **o padrão.** O mais rápido que passou nos
  testes, bom em tarefa mecânica e delimitada
- `opencode/ling-3.1-flash-free`
- `opencode/nemotron-3.5-lightning-free`
- `opencode/nemotron-3-ultra-free`
- `opencode/step-5-preview-free`
- `opencode/longcat-2.5-preview-free`

Para ligar: `opencode auth login` e escolher o provedor zen. É um fluxo
interativo no terminal — não dá para automatizar, e não precisa de cartão.

### OpenRouter (faixa `nex`)

15 modelos `:free` no momento. Os que fazem sentido como executor de código:

| Modelo | Contexto | Por quê |
|---|---|---|
| `poolside/laguna-s-2.1:free` | 262k | **o padrão de hoje.** Agente de código, 118B de parâmetros com 8B ativos, 70,2% no Terminal-Bench 2.1 |
| `cohere/north-mini-code:free` | 256k | primeiro modelo agêntico de código da Cohere, 30B com 3B ativos. Leve e específico |
| `thinkingmachines/inkling:free` | 1048k | contexto enorme. Serve quando a tarefa exige ler muito antes de escrever |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262k | alternativa de porte maior |

Para ligar: crie uma chave em [openrouter.ai](https://openrouter.ai) e grave em
`~/.config/unity/openrouter.key`. Sem ela a faixa nem roda — volta na hora
dizendo que falta a credencial, o que é chave faltando e não falha de modelo.

> O nome da faixa é `nex` por causa do modelo que ela usava quando nasceu. O
> flag continua `--nivel nex` porque trocar quebraria o hábito de quem já usa;
> leia como "a faixa grátis da OpenRouter".

## O que "grátis" custa

Não é almoço de graça. O que você paga em vez de dinheiro:

- **Velocidade.** As faixas grátis são mais lentas, e a `nex` é a mais lenta das
  duas porque raciocina mais antes de escrever. Não sirva com ela o que a pessoa
  está esperando na hora.
- **Limite de uso.** Provedor gratuito limita requisições por minuto e por dia.
  Tarefa muito longa pode bater no teto no meio.
- **Julgamento.** Modelo pequeno segue instrução bem e **decide mal**. Dê a ele
  tarefa onde a decisão já foi tomada. "Escreva teste para este módulo" funciona;
  "resolva este bug" não.
- **Privacidade.** Modelo gratuito muitas vezes é gratuito porque o provedor usa
  os dados. **Não mande código de cliente nem segredo** para faixa grátis se
  isso for problema no seu caso. Leia a política do provedor — na OpenRouter é
  configurável por conta.
- **Estabilidade do nome.** O catálogo rotaciona, como descrito acima.

## Revisão cruzada: de graça, a conferência também

Quando uma faixa grátis termina, **o outro modelo grátis** lê o que foi feito (o
diff, ou os arquivos novos) e carimba `APROVADO`, `RESSALVAS` ou `PROBLEMAS` no
aviso. Existe porque "terminou" nunca significou "ficou bom", e porque revisar
custa zero quando o revisor também é grátis.

Três coisas para não errar:

- **Não peça revisão no prompt da tarefa.** Já acontece depois, sozinho.
- **O veredito é opinião de modelo pequeno, não laudo.** `PROBLEMAS` merece você
  abrir e olhar; `APROVADO` não dispensa conferir se o arquivo está no disco.
- **Revisão ausente não é reprovação.** Se o relógio dela estourar, a entrega
  sai sem veredito de propósito — conferência não atrasa entrega.

## Duas travas que vão te morder se você não souber

**`opencode` e `nex` não rodam em paralelo entre si.** Usam o mesmo binário e o
mesmo banco de estado; a segunda volta na hora com "database is locked". O
despachante serializa as duas numa fila só. Paralelismo de verdade só entre
faixas de binários diferentes.

**`ok: false` não prova que o trabalho falhou.** Já aconteceu um site inteiro,
funcionando, voltar marcado como falha porque o executor deixou um servidor de
teste em primeiro plano e estourou o relógio do shell. Suspeite sempre que a
duração ficar bem abaixo do tempo limite: abra e olhe antes de descartar.

## Escrever a tarefa em inglês, entregar em português

O prompt da delegação vai em **inglês**; o executor recebe instrução automática
de devolver o resumo final em português. Motivo: português custa mais token que
inglês para dizer a mesma coisa, e num sistema que delega e recebe relatório
cada salto paga esse câmbio. O que importa é o idioma da **entrega**, não o do
processo.

## O executor começa cego

Ele não viu a sua conversa, não conhece o projeto, e tem limite de tamanho no
argumento. Então o prompt precisa carregar, curto:

1. o que fazer, em uma ou duas frases;
2. o **caminho absoluto** do projeto;
3. o contexto que só você tem — o que foi decidido antes, o que não mexer.

E uma lição que custou 438 linhas de trabalho perdido: em tarefa grande, peça
**commit por etapa**. Delegação que estoura o relógio sem ter comitado nada
perde tudo o que fez.
