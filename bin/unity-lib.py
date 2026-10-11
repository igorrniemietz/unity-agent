#!/usr/bin/env python3
"""Peças comuns do supervisor: Telegram, filtro de segredos e ai-memory.

Importado por unity-notify-telegram e unity-digest.
"""
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

TELEGRAM_ENV = Path.home() / "infra/telegram/.env"
AI_MEMORY_ENV = Path.home() / "infra/ai-memory/.env"
ROUTER = "http://127.0.0.1:8787"
AI_MEMORY = "http://127.0.0.1:49374"

TELEGRAM_LIMIT = 3800  # abaixo do teto real de 4096, com folga para o rodapé

# Última linha de defesa antes de qualquer coisa sair para o Telegram. O
# sanitizador do ai-memory é server-side e não cobre o texto livre que o hook
# Stop entrega em last_assistant_message.
SECRETS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_\-]{30,}"),      # token de bot do Telegram
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[a-zA-Z][\w+.\-]*://[^:/\s]+:[^@\s]+@"),  # user:senha@host
    re.compile(r"\b[a-f0-9]{64}\b"),                        # token do ai-memory
    re.compile(r"(?i)\bUser Data\b"),
    re.compile(r"(?i)\b[A-Z][A-Z0-9_]*_(KEY|TOKEN|SECRET|PASSWORD)\s*[=:]\s*\S+"),
]


def read_env(path, key):
    try:
        for line in open(path):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def has_secret(text):
    return any(rx.search(text or "") for rx in SECRETS)



# ─── Trava de idioma ────────────────────────────────────────────────────────
# Em 19/08/2026 a Unity mandou uma mensagem em japonês no Telegram. A causa não
# importa para esta trava, e é justamente esse o ponto: qualquer degrau da
# cascata pode devolver outro idioma (o qwen2.5:3b do Ollama é o mais provável,
# mas a deepseek e os modelos grátis do opencode zen também já fizeram isso).
#
# Pedir "responda em português" no prompt já estava feito e não bastou — é
# instrução, e instrução o modelo pode ignorar. Isto aqui é trava de FERRAMENTA:
# roda no ponto de saída, depois de qualquer modelo, e não tem como ser
# convencida. Ver a memória feedback_trava_de_ferramenta_nao_de_prompt.
NAO_LATINO = re.compile(
    "["
    "\u3040-\u309f"    # hiragana
    "\u30a0-\u30ff"    # katakana
    "\u3400-\u4dbf"    # CJK extensão A
    "\u4e00-\u9fff"    # CJK unificado (han)
    "\uf900-\ufaff"    # CJK compatibilidade
    "\uac00-\ud7af"    # hangul
    "\u0400-\u04ff"    # cirílico
    "\u0600-\u06ff"    # árabe
    "\u0e00-\u0e7f"    # tailandês
    "\u0900-\u097f"    # devanágari
    "]"
)

# Limiar em CARACTERES ABSOLUTOS, não em proporção. Proporção deixaria passar um
# parágrafo inteiro em japonês dentro de uma mensagem longa, que é exatamente o
# caso ruim. Três é folga para um nome próprio ou um caractere citado de
# propósito ("o arquivo se chama 東京.txt"); quatro já é frase.
IDIOMA_LIMITE = 3


def idioma_suspeito(texto):
    """Devolve o trecho ofensor se o texto tem escrita não-latina demais.

    Devolve None quando o texto está limpo. Nunca levanta exceção — uma trava
    que quebra é uma trava que some.
    """
    try:
        achados = NAO_LATINO.findall(texto or "")
        if len(achados) <= IDIOMA_LIMITE:
            return None
        m = NAO_LATINO.search(texto)
        ini = max(m.start() - 20, 0)
        return (texto[ini:m.start() + 40] or "").strip()
    except Exception:
        return None


def _registrar_idioma(texto, trecho):
    """Grava o incidente em disco. Sem isto a trava vira censura silenciosa e
    ninguém descobre QUAL degrau está devolvendo japonês."""
    try:
        alvo = Path.home() / ".local/share/unity-supervisor"
        alvo.mkdir(parents=True, exist_ok=True)
        with open(alvo / "idioma-barrado.jsonl", "a") as fh:
            fh.write(json.dumps({
                "quando": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "trecho": trecho,
                "texto": (texto or "")[:600],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def clean(text):
    """Suprime a mensagem inteira se houver suspeita de segredo.

    Redigir trecho a trecho seria mais amigável e menos seguro: um padrão que
    eu não previ passaria batido. Suprimir tudo falha para o lado seguro.
    """
    if has_secret(text):
        return "[conteúdo suprimido: possível segredo detectado]"
    return text


def truncate(text, limit=TELEGRAM_LIMIT):
    if len(text) <= limit:
        return text
    head = text[:limit].rsplit("\n", 1)[0]
    omitted = text[len(head):].count("\n") + 1
    return head + f"\n… (+{omitted} linhas)"


def rodape_uso():
    """Roda 'unity-uso --linha' e devolve as duas linhas de rodapé, ou None.

    Nunca levanta exceção: isto é um extra cosmético anexado à mensagem
    principal, uma falha aqui não pode derrubar o envio ao Telegram.
    """
    try:
        r = subprocess.run(
            ["/home/reaper/.local/bin/unity-uso", "--linha"],
            capture_output=True, text=True, timeout=30)
        saida = r.stdout.strip()
        return saida or None
    except Exception:
        return None


TELEGRAM_FALHAS = Path.home() / ".local/share/unity-supervisor/telegram-falhas.log"


def _registrar_falha_telegram(texto, erro):
    # Medido em 04/08: uma notificação de conclusão de delegação sumiu sem
    # deixar rastro nenhum — `send_telegram` "nunca levanta exceção" também
    # queria dizer "nunca avisa ninguém quando falha". Uma falha sem log é
    # indistinguível de "nada aconteceu", e foi exatamente essa ambiguidade
    # que custou a investigação. Isto não conserta a falha (é best-effort,
    # a mesma promessa de nunca lançar exceção), só garante que ela apareça
    # em algum lugar em vez de só desaparecer.
    try:
        TELEGRAM_FALHAS.parent.mkdir(parents=True, exist_ok=True)
        with open(TELEGRAM_FALHAS, "a") as fh:
            import datetime
            fh.write(f"{datetime.datetime.now().isoformat()} {erro!r} "
                     f"texto={texto[:200]!r}\n")
    except Exception:
        pass


def send_telegram(text, silent=True, rodape=False, bruto=None):
    """Envia ao Telegram. Devolve True/False; nunca levanta exceção.

    Tenta até 3 vezes (0s/2s/5s) antes de desistir — POST único sem retry
    trata um soluço de rede transitório como "a mensagem não existia", e é
    justamente esse tipo de falha (rara, silenciosa, sem log) que fez uma
    conclusão de delegação sumir em 04/08/2026 sem o dono nunca saber.
    """
    token = read_env(TELEGRAM_ENV, "TELEGRAM_BOT_TOKEN")
    chat = read_env(TELEGRAM_ENV, "TELEGRAM_CHAT_ID")
    if not token or not chat:
        _registrar_falha_telegram(text, "sem token/chat_id configurado")
        return False
    corpo = truncate(clean(text))

    # Trava de idioma. Vem DEPOIS do clean (para não vazar segredo no log do
    # incidente) e ANTES do rodapé (que é gerado por código e é sempre latino).
    trecho = idioma_suspeito(corpo)
    if trecho:
        _registrar_idioma(corpo, trecho)
        alternativa = truncate(clean(bruto)) if bruto else None
        if alternativa and not idioma_suspeito(alternativa):
            # Caminho normal: quem resumiu com LLM guardou o texto original.
            # Melhor mandar o cru longo que uma mensagem que o dono não lê.
            corpo = alternativa
        else:
            corpo = ("\u26a0\ufe0f Resposta barrada: saiu fora do\n"
                     "portugues. Detalhe em\n"
                     "~/.local/share/unity-supervisor/\n"
                     "idioma-barrado.jsonl")

    if rodape:
        # Rodapé vai DEPOIS do truncate/clean, para nunca ser cortado junto
        # com o texto principal nem disparar a supressão por segredo.
        pe = rodape_uso()
        if pe:
            corpo = corpo + "\n\n" + pe
    body = json.dumps({
        "chat_id": chat,
        "text": corpo,
        # Sem parse_mode de propósito: MarkdownV2 exige escapar 18 caracteres e
        # um "." solto num nome de arquivo derruba a mensagem com HTTP 400.
        "disable_notification": silent,
        # Impede o Telegram de fazer GET numa URL que tenha escapado do filtro.
        "link_preview_options": {"is_disabled": True},
    }).encode()

    import time
    ultimo_erro = None
    for tentativa, espera in enumerate((0, 2, 5)):
        if espera:
            time.sleep(espera)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                ultimo_erro = f"HTTP {resp.status}"
        except Exception as exc:
            ultimo_erro = repr(exc)
    _registrar_falha_telegram(text, ultimo_erro)
    return False


def send_telegram_document(path, caption=""):
    """Uploads a file to Telegram via sendDocument API using multipart/form-data.

    Returns True on success, False on failure; never raises an exception.
    """
    try:
        token = read_env(TELEGRAM_ENV, "TELEGRAM_BOT_TOKEN")
        chat = read_env(TELEGRAM_ENV, "TELEGRAM_CHAT_ID")
        if not token or not chat:
            return False

        file_path = Path(path)
        if not file_path.is_file():
            return False

        filename = file_path.name
        file_bytes = file_path.read_bytes()

        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()

        def add_field(name, val):
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(f"{val}\r\n".encode("utf-8"))

        add_field("chat_id", chat)
        if caption:
            add_field("caption", clean(caption))

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(file_bytes)
        body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status == 200
    except Exception:
        return False


def mcp(tool, arguments, timeout=30):
    """Chama uma ferramenta MCP do ai-memory. Devolve dict ou None."""
    token = read_env(AI_MEMORY_ENV, "AI_MEMORY_AUTH_TOKEN")
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }).encode()
    req = urllib.request.Request(
        AI_MEMORY + "/mcp", data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode(errors="replace")
    except Exception:
        return None
    # A resposta pode vir como SSE (data: {...}) ou JSON puro.
    for chunk in raw.splitlines():
        chunk = chunk[5:].strip() if chunk.startswith("data:") else chunk.strip()
        if not chunk.startswith("{"):
            continue
        try:
            msg = json.loads(chunk)
        except Exception:
            continue
        content = (msg.get("result") or {}).get("content") or []
        for item in content:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except Exception:
                    return {"text": item["text"]}
    return None


def _uma_chamada(prompt, client, max_tokens, timeout):
    body = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        f"{ROUTER}/{client}/v1/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return None, str(exc)[:200], {}
    choices = data.get("choices") or [{}]
    texto = (choices[0].get("message") or {}).get("content", "")
    return texto, None, (data.get("usage") or {})


# Teto de seguranca do reforco: 3x o pedido, no maximo 6000. Sem teto, um prompt
# que faz o modelo divagar viraria uma conta aberta.
TETO_REFORCO = 6000


def llm(prompt, client="supervisor", max_tokens=1200, timeout=180):
    """Chama o llm-router. O roteador escolhe o provedor conforme o orçamento.

    Devolve (texto, erro). Se o modelo gastar TODO o orçamento raciocinando e
    não sobrar nada para a resposta, tenta uma vez com o triplo antes de desistir.

    Por que isto existe (medido em 10/09/2026): o `unity-digest` falhou 10 vezes
    em 7 dias — praticamente toda execução — com a mensagem inútil
    "falha ao gerar o digest: None". No ledger do llm-router, as chamadas eram

        completion_tokens=1500  reasoning_tokens=1500  visivel=0   $0,0015

    ou seja, o deepseek-v4-flash consumia os 1500 tokens INTEIROS pensando e era
    cortado antes de escrever a primeira letra — e cobrava por isso. O
    `reasoning_effort: low` do providers.json já estava sendo enviado; ele reduz
    o raciocínio, não o elimina, e o tamanho dele varia com o volume de dados do
    prompt. Nos dias de mais projetos, estourava.

    O erro era `None` porque a API não falha nesse caso: devolve 200 com
    `content: ""`. Por isso passou dias despercebido — o caller via "erro None" e
    não tinha como saber que a causa era orçamento de tokens. Agora o erro DIZ o
    que aconteceu, e o reforço resolve sozinho na maioria das vezes.
    """
    texto, erro, uso = _uma_chamada(prompt, client, max_tokens, timeout)
    if erro:
        return None, erro
    if texto and texto.strip():
        return texto, None

    # Veio 200 com texto vazio. Foi orçamento estourado no raciocínio?
    pensou = (uso.get("completion_tokens_details") or {}).get("reasoning_tokens") \
        or uso.get("reasoning_tokens") or 0
    if pensou < max_tokens * 0.8:
        return None, (f"o modelo devolveu texto vazio (raciocinou {pensou} de "
                      f"{max_tokens} tokens) — não foi orçamento")

    reforco = min(max_tokens * 3, TETO_REFORCO)
    if reforco <= max_tokens:
        return None, (f"o modelo gastou os {max_tokens} tokens raciocinando e não "
                      f"escreveu nada; o teto de reforço ({TETO_REFORCO}) já foi usado")
    texto, erro, uso2 = _uma_chamada(prompt, client, reforco, timeout)
    if erro:
        return None, f"{erro} (na 2a tentativa, com {reforco} tokens)"
    if texto and texto.strip():
        return texto, None
    pensou2 = (uso2.get("completion_tokens_details") or {}).get("reasoning_tokens") \
        or uso2.get("reasoning_tokens") or 0
    return None, (f"o modelo gastou {pensou} tokens raciocinando em {max_tokens} e "
                  f"{pensou2} em {reforco}, sem escrever nada nas duas vezes")
