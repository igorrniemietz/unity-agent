#!/usr/bin/env python3
"""Bateria do unity-block-delete.

BARRA  = espera deny.  PASSA = espera silêncio (exit 0, stdout vazio).
Roda contra o script instalado, pelo stdin/stdout reais do contrato de hook —
não importa o módulo, para testar o que o Claude Code de fato executa.
"""
import json, os, subprocess, sys

HOOK = os.environ.get("UNITY_HOOK_PATH", "/home/reaper/.local/bin/unity-block-delete")

def decide(cmd):
    p = subprocess.run([HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        text=True, capture_output=True,
        env={"UNITY_HOOK_NO_NOTIFY": "1", "PATH": "/usr/bin:/bin"})
    if not p.stdout.strip():
        return "PASSA"
    try:
        return "BARRA" if json.loads(p.stdout)["hookSpecificOutput"][
            "permissionDecision"] == "deny" else "PASSA"
    except Exception:
        return "ERRO"

CASOS = [
    # --- segredo de verdade: tem de continuar barrado ---
    ("BARRA", "cat /home/reaper/infra/ai-memory/.env", "ler .env direto"),
    ("BARRA", "cat ~/.ssh/id_rsa", "ler chave ssh"),
    ("BARRA", "cp /home/reaper/.ssh/id_rsa /tmp/x", "copiar chave ssh"),
    ("BARRA", 'grep -r "KEY" /home/reaper/infra/llm-router/.env', "grep no .env"),
    ("BARRA", "python3 -c \"print(open('/home/reaper/infra/ai-memory/.env').read())\"",
     "ler .env por dentro do python"),
    ("BARRA", "source /home/reaper/infra/ai-memory/.env", "carregar .env no shell"),
    ("BARRA", "tail -5 < /home/reaper/infra/ai-memory/.env", "ler .env por redirecionamento"),
    ("BARRA", "base64 /home/reaper/infra/x/.env.local", "exfiltrar .env.local"),
    ("BARRA", "cat /home/reaper/infra/certs/server.key", "ler chave privada"),
    ("BARRA", "cat /home/reaper/infra/gcp/credentials.json", "ler credencial"),

    # --- o falso positivo que travou a Unity: citar caminho em texto ---
    ("PASSA", 'unity-despachar --nivel claude --projeto relatorio --dir /home/reaper '
              '"leia os logs em /home/reaper/infra/llm-router e use tail para medir o custo"',
     "despacho citando path + verbo dentro das aspas"),
    ("PASSA", 'unity-despachar --projeto x "o config fica em /home/reaper/infra/ai-memory/.env, '
              'mas voce nao precisa abrir"',
     "despacho citando .env em prosa"),
    ("PASSA", 'unity-despachar --projeto x "produza um relatorio com curl, grep e python"',
     "despacho citando verbos sem segredo"),
    # Este é o caso que ISOLA o discriminador de token: a prosa tem um segredo
    # (.env) E um verbo de leitura (tail), mas longe um do outro, e o comando de
    # verdade é o unity-despachar. O critério antigo (linha inteira) barra; o
    # novo (token com espaço = prosa) deixa passar. Sem ele a bateria fica verde
    # mesmo com a lógica antiga de volta — foi o que a sabotagem 2 revelou.
    ("PASSA", 'unity-despachar --projeto x "use tail nos logs do roteador para medir '
              'o custo, e depois diga se o .env do ai-memory precisa de ajuste"',
     "despacho com segredo E verbo na prosa, separados"),

    # --- ~/infra que NAO e segredo: liberado apos a decisao do dono ---
    ("PASSA", "tail -100 /home/reaper/infra/llm-router/router.log", "ler log do roteador"),
    ("PASSA", "cat /home/reaper/infra/ai-memory/docker-compose.yml", "ler compose"),
    ("PASSA", "ls /home/reaper/infra/llm-router/", "listar pasta da infra"),

    # --- exclusao: comportamento tem de continuar igual ---
    ("BARRA", "rm -rf /tmp/x", "rm"),
    ("BARRA", "cd /tmp && rm -rf x", "rm depois de &&"),
    ("BARRA", "git clean -fd", "git clean"),
    ("BARRA", "find . -name '*.tmp' -delete", "find -delete"),
    ("PASSA", "unity-trash /tmp/x", "a alternativa autorizada"),
    ("PASSA", "ls -la /tmp", "comando inocente"),
    ("PASSA", 'echo "vou remover isso depois"', "a palavra remover em texto"),
]

def main():
    falhas = []
    for esperado, cmd, nome in CASOS:
        obtido = decide(cmd)
        ok = obtido == esperado
        if not ok:
            falhas.append((nome, esperado, obtido, cmd))
        print(f"  {'ok ' if ok else 'FALHA'} [{obtido:5s}] {nome}")
    print()
    if falhas:
        print(f"{len(falhas)} FALHA(S):")
        for nome, esp, obt, cmd in falhas:
            print(f"  - {nome}: esperava {esp}, veio {obt}\n      {cmd[:110]}")
        sys.exit(1)
    print(f"todos os {len(CASOS)} casos passaram")

main()
