#!/usr/bin/env bash
# Instala a Unity: scripts, units e prompts, com os caminhos reescritos para o
# $HOME de quem está instalando.
#
# Idempotente: rodar de novo sobrescreve os arquivos e recarrega o systemd, mas
# não duplica nada nem apaga config sua (access.json, .env e projetos.md são
# preservados se já existirem).
set -euo pipefail

ORIGEM_HOME="/home/reaper"   # o $HOME em que estes arquivos foram escritos
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN="$HOME/.local/bin"
UNITS="$HOME/.config/systemd/user"
PROMPTS="$HOME/.claude/orquestrador"

mkdir -p "$BIN" "$UNITS" "$PROMPTS" "$HOME/.claude/channels/telegram" \
         "$HOME/.local/share/unity-supervisor" "$HOME/.local/share/unity-orquestrador"

reescrever() { sed "s|$ORIGEM_HOME|$HOME|g" "$1" > "$2"; }

echo "→ scripts em $BIN"
for f in "$REPO"/bin/unity-*; do
  destino="$BIN/$(basename "$f")"
  reescrever "$f" "$destino"
  chmod +x "$destino"
done

echo "→ units em $UNITS"
for f in "$REPO"/systemd/unity-*; do
  reescrever "$f" "$UNITS/$(basename "$f")"
done

echo "→ prompts em $PROMPTS"
for f in persona.md roteamento.md; do
  reescrever "$REPO/prompts/$f" "$PROMPTS/$f"
done
if [ ! -f "$PROMPTS/projetos.md" ]; then
  reescrever "$REPO/prompts/projetos.example.md" "$PROMPTS/projetos.md"
  echo "  projetos.md criado a partir do exemplo — edite antes de usar"
else
  echo "  projetos.md já existe, preservado"
fi

echo "→ settings da Unity"
reescrever "$REPO/config/unity-settings.json" "$HOME/.claude/supervisor-settings.json"

if [ ! -f "$HOME/.claude/channels/telegram/access.json" ]; then
  cp "$REPO/config/telegram-access.example.json" \
     "$HOME/.claude/channels/telegram/access.json"
  chmod 600 "$HOME/.claude/channels/telegram/access.json"
  echo "  access.json criado a partir do exemplo — ponha o seu ID de usuário"
fi

# O caminho do `claude` é fixo na unit do daemon porque o systemd não herda o
# PATH do shell. Descobrir aqui evita a unit apontar para um nó que não existe.
CLAUDE_BIN="$(command -v claude || true)"
if [ -n "$CLAUDE_BIN" ]; then
  sed -i "s|ExecStart=.*claude daemon run|ExecStart=$CLAUDE_BIN daemon run|" \
      "$UNITS/unity-daemon.service"
  sed -i "s|^Environment=PATH=.*|Environment=PATH=$(dirname "$CLAUDE_BIN"):$BIN:/usr/bin:/bin|" \
      "$UNITS/unity-daemon.service"
  echo "→ daemon apontado para $CLAUDE_BIN"
else
  echo "  AVISO: 'claude' não está no PATH — ajuste unity-daemon.service à mão"
fi

systemctl --user daemon-reload
systemctl --user enable --now unity-daemon.service
systemctl --user enable --now unity-supervisor.timer unity-costs.timer \
        unity-digest.timer unity-alerta-ai-memory.timer unity-pendencias.timer

echo
echo "Instalado. Falta:"
echo "  1. token do bot em ~/.claude/channels/telegram/.env (TELEGRAM_BOT_TOKEN=...)"
echo "  2. seu ID de usuário em ~/.claude/channels/telegram/access.json"
echo "  3. descrever seus projetos em ~/.claude/orquestrador/projetos.md"
echo "  4. systemctl --user start unity-supervisor.service"
