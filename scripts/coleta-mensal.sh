#!/bin/bash
# Coleta mensal automática - roda dia 1 de cada mês via launchd.
# Puxa nomeações do mês anterior + sincroniza cadastro de peritos.

set -e

REPO_DIR="$HOME/nomeacoes"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/mensal-$(date +%Y%m).log"

cd "$REPO_DIR"
source .venv/bin/activate

echo "===== $(date '+%Y-%m-%d %H:%M:%S') START =====" >> "$LOG"

# 1. Coleta nomeações do mês anterior
python -m src.cli coletar-mes-anterior >> "$LOG" 2>&1

# 2. Atualiza cadastro de peritos (novos podem ter sido cadastrados)
python -m src.cli sincronizar-peritos >> "$LOG" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') END =====" >> "$LOG"
