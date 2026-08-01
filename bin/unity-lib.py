#!/usr/bin/env python3
"""Peças comuns do supervisor: Telegram, filtro de segredos e ai-memory.

Importado por unity-notify-telegram e unity-digest.
"""
import json
import os
import re
import urllib.error
import urllib.request
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


def send_telegram(text, silent=True):
    """Envia ao Telegram. Devolve True/False; nunca levanta exceção."""
    token = read_env(TELEGRAM_ENV, "TELEGRAM_BOT_TOKEN")
    chat = read_env(TELEGRAM_ENV, "TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    body = json.dumps({
        "chat_id": chat,
        "text": truncate(clean(text)),
        # Sem parse_mode de propósito: MarkdownV2 exige escapar 18 caracteres e
        # um "." solto num nome de arquivo derruba a mensagem com HTTP 400.
        "disable_notification": silent,
        # Impede o Telegram de fazer GET numa URL que tenha escapado do filtro.
        "link_preview_options": {"is_disabled": True},
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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


def llm(prompt, client="supervisor", max_tokens=1200, timeout=180):
    """Chama o llm-router. O roteador escolhe o provedor conforme o orçamento."""
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
        return None, str(exc)[:200]
    choices = data.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content", ""), None
