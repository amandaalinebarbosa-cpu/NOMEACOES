#!/bin/bash
# Instala launchd para Flask + ngrok (autostart + autorestart).
# Rode no Mac: bash scripts/instalar-launchd.sh

set -e

USER_HOME="$HOME"
BASE="$USER_HOME/nomeacoes"
PY="$BASE/.venv/bin/python"
NGROK=$(which ngrok)
AGENTS="$USER_HOME/Library/LaunchAgents"

mkdir -p "$AGENTS" "$BASE/logs"

echo "→ Caminhos detectados:"
echo "   Python venv: $PY"
echo "   ngrok      : $NGROK"
echo "   Projeto    : $BASE"
echo

if [ ! -x "$PY" ]; then
  echo "ERRO: $PY não encontrado. Ative o venv e tente de novo."
  exit 1
fi
if [ -z "$NGROK" ]; then
  echo "ERRO: ngrok não está no PATH. Instale com: brew install ngrok"
  exit 1
fi

# ---------------- Flask ----------------
cat > "$AGENTS/com.peritusdominus.flask.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>              <string>com.peritusdominus.flask</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>-m</string>
        <string>src.cli</string>
        <string>web</string>
    </array>
    <key>WorkingDirectory</key>   <string>$BASE</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$BASE/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>          <true/>
    <key>KeepAlive</key>          <true/>
    <key>StandardOutPath</key>    <string>$BASE/logs/flask.out.log</string>
    <key>StandardErrorPath</key>  <string>$BASE/logs/flask.err.log</string>
</dict>
</plist>
EOF

# ---------------- ngrok ----------------
cat > "$AGENTS/com.peritusdominus.ngrok.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>              <string>com.peritusdominus.ngrok</string>
    <key>ProgramArguments</key>
    <array>
        <string>$NGROK</string>
        <string>start</string>
        <string>--config</string>
        <string>$BASE/ngrok.yml</string>
        <string>dashboard</string>
    </array>
    <key>WorkingDirectory</key>   <string>$BASE</string>
    <key>RunAtLoad</key>          <true/>
    <key>KeepAlive</key>          <true/>
    <key>StandardOutPath</key>    <string>$BASE/logs/ngrok.out.log</string>
    <key>StandardErrorPath</key>  <string>$BASE/logs/ngrok.err.log</string>
</dict>
</plist>
EOF

echo "→ Matando processos antigos (se houver)…"
pkill -f "src.cli web" 2>/dev/null || true
pkill -f "ngrok start" 2>/dev/null || true
sleep 2

echo "→ Descarregando versões antigas do launchd (se houver)…"
launchctl bootout gui/$(id -u)/com.peritusdominus.flask 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.peritusdominus.ngrok 2>/dev/null || true

echo "→ Carregando serviços…"
launchctl bootstrap gui/$(id -u) "$AGENTS/com.peritusdominus.flask.plist"
launchctl bootstrap gui/$(id -u) "$AGENTS/com.peritusdominus.ngrok.plist"

echo "→ Habilitando restart automático…"
launchctl enable gui/$(id -u)/com.peritusdominus.flask
launchctl enable gui/$(id -u)/com.peritusdominus.ngrok

sleep 3

echo
echo "✓ Instalado. Verificação:"
launchctl list | grep peritusdominus || true
echo
echo "Logs:"
echo "   tail -f $BASE/logs/flask.err.log"
echo "   tail -f $BASE/logs/ngrok.err.log"
echo
echo "Testar:"
echo "   curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:5001"
echo "   curl -s -o /dev/null -w 'HTTP %{http_code}\n' https://peso-unbaked-hydrogen.ngrok-free.dev"
