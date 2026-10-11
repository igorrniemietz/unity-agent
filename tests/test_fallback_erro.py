#!/usr/bin/env python3
"""Bateria do tratamento de erro de API no unity-fallback.

Regressão de 03/08: o opencode zen devolveu HTTP 402 "Insufficient Balance" (o
saldo é do upstream deles, não do dono) e o dono recebeu no Telegram o JSON do
erro inteiro — `responseBody` e cabeçalhos do Cloudflare inclusive. Causa: só
eventos `type == "text"` eram lidos; sem texto, a rede de segurança despejava a
saída crua.

Importa o módulo em vez de rodar o binário porque o que está sob teste é a
escolha de modelo, e o alvo é justamente o `subprocess.run` que chamaria a API.
"""
import importlib.util as u
import json
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ALVO = "/home/reaper/.local/bin/unity-fallback"

spec = u.spec_from_file_location("fb", ALVO, loader=SourceFileLoader("fb", ALVO))
fb = u.module_from_spec(spec)
spec.loader.exec_module(fb)

ERRO_402 = json.dumps({
    "type": "error", "timestamp": 1785726304837, "sessionID": "ses_x",
    "error": {"name": "APIError", "data": {
        "message": "Upstream request failed: [invalid_request_error] "
                   "Insufficient Balance",
        "statusCode": 402, "isRetryable": False,
        "responseHeaders": {"cf-ray": "a252199addfff3c9-CMH"},
        "responseBody": "{\"error\":{\"message\":\"Insufficient Balance\"}}"}}})

TEXTO_OK = json.dumps({
    "type": "text", "part": {"type": "text", "text": "Deleguei pro Gemini."}})

tmp = Path(tempfile.mkdtemp())
fb.TRABALHO = tmp
fb.SESSAO = tmp / "sessao.json"
fb.MODELOS_RESERVA = ["opencode/reserva-a", "opencode/reserva-b"]

chamadas = []


def falso_opencode(saidas):
    """subprocess.run de mentira: emite `saidas` na ordem, uma por chamada."""
    seq = list(saidas)

    def run(cmd, **kw):
        chamadas.append(cmd[cmd.index("--model") + 1])
        return subprocess.CompletedProcess(
            cmd, 0, stdout=(seq.pop(0) if seq else ""), stderr="")
    return run


def caso(nome, saidas, espera_modelos, espera_em):
    global chamadas
    chamadas = []
    fb.subprocess.run = falso_opencode(saidas)
    r = fb.responder("melhora o visual do jobcraft")
    if "responseBody" in r:
        print(f"[FALHA] {nome}: vazou JSON cru para o Telegram")
        return False
    ok = chamadas == espera_modelos and espera_em in r
    print(f"[{'OK ' if ok else 'FALHA'}] {nome}")
    if not ok:
        print(f"        modelos:  {chamadas} (esperado {espera_modelos})")
        print(f"        resposta: {r[:200]}")
    return ok


todos = [
    # O caso real do 402: frase humana, nunca o JSON.
    caso("402 em todos os modelos -> frase humana",
         [ERRO_402, ERRO_402, ERRO_402],
         [fb.MODELO, "opencode/reserva-a", "opencode/reserva-b"],
         "saldo do provedor deles"),
    # Recusa do principal não pode calar o canal.
    caso("402 no principal -> a reserva responde",
         [ERRO_402, TEXTO_OK],
         [fb.MODELO, "opencode/reserva-a"],
         "Deleguei pro Gemini"),
    # A reserva é para falha, não para todo pedido: sem erro, ninguém a chama.
    caso("sucesso no principal -> nenhuma reserva",
         [TEXTO_OK], [fb.MODELO], "Deleguei pro Gemini"),
    # Formato desconhecido continua caindo na saída crua: trocar de modelo não
    # conserta parser, e canal mudo é pior que resposta feia.
    caso("formato desconhecido -> saída crua, sem reserva",
         ['{"type":"step_start"}\nbanana'], [fb.MODELO], "banana"),
]

# Sabotagem: cegar o `extrair_erro` tem que fazer o primeiro caso vazar de novo.
# Sem isto, um teste que passa não prova que a correção é quem o faz passar.
print("\n--- sabotagem: extrair_erro cego ---")
fb.extrair_erro = lambda saida: None
chamadas = []
fb.subprocess.run = falso_opencode([ERRO_402])
vazou = "responseBody" in fb.responder("x")
print(f"[{'OK ' if vazou else 'FALHA'}] sem extrair_erro o JSON volta a vazar")
todos.append(vazou)

print("\nRESULTADO:", "TUDO OK" if all(todos) else "HÁ FALHAS")
sys.exit(0 if all(todos) else 1)
