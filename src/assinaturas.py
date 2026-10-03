"""Gestão de assinantes do Peritus Dominus — Nomeações SIGEO.

Lida com:
  * Webhook da Kiwify (compra, cancelamento, reembolso, chargeback).
  * Regeração do arquivo ngrok.yml com a lista de e-mails ativos.
  * Reload do túnel ngrok (via launchctl, SIGHUP ou kill+restart).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
from pathlib import Path

import yaml

from .db import connect

log = logging.getLogger(__name__)

NGROK_YML = Path(os.environ.get("NGROK_YML", str(Path.home() / "nomeacoes" / "ngrok.yml")))
NGROK_TUNNEL_NAME = os.environ.get("NGROK_TUNNEL_NAME", "dashboard")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "amandaalinebarbosa@gmail.com")

# Eventos da Kiwify que concedem acesso
EVENTOS_LIBERA = {"order_approved", "subscription_approved", "subscription_renewed"}
# Eventos que removem acesso
EVENTOS_REMOVE = {
    "order_refunded", "order_chargeback",
    "subscription_canceled", "subscription_late",
}


# ----------------------------- banco de dados ----------------------------- #

def upsert_assinante(email: str, nome: str | None, order_id: str | None,
                      produto: str | None, status: str, raw: dict) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO assinante (email, nome, status, kiwify_order_id,
                                   kiwify_product, raw, atualizado_em,
                                   cancelado_em)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(),
                    CASE WHEN %s <> 'ativo' THEN NOW() ELSE NULL END)
            ON CONFLICT (email) DO UPDATE SET
                nome            = COALESCE(EXCLUDED.nome, assinante.nome),
                status          = EXCLUDED.status,
                kiwify_order_id = COALESCE(EXCLUDED.kiwify_order_id,
                                            assinante.kiwify_order_id),
                kiwify_product  = COALESCE(EXCLUDED.kiwify_product,
                                            assinante.kiwify_product),
                raw             = EXCLUDED.raw,
                atualizado_em   = NOW(),
                cancelado_em    = CASE WHEN EXCLUDED.status <> 'ativo'
                                       THEN NOW() ELSE NULL END
            """,
            (email.lower().strip(), nome, status, order_id, produto,
             json.dumps(raw, ensure_ascii=False, default=str), status),
        )
        conn.commit()


def log_evento(evento: str | None, email: str | None, payload: dict) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO assinante_evento (evento, email, payload) VALUES (%s, %s, %s::jsonb)",
            (evento, email, json.dumps(payload, ensure_ascii=False, default=str)),
        )
        conn.commit()


def listar_ativos() -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT email, nome, status, kiwify_order_id,
                   criado_em, atualizado_em
            FROM assinante
            WHERE status = 'ativo'
            ORDER BY criado_em DESC
            """
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def listar_todos() -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT email, nome, status, kiwify_order_id,
                   criado_em, atualizado_em, cancelado_em
            FROM assinante
            ORDER BY criado_em DESC
            """
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ----------------------------- ngrok.yml ----------------------------- #

def _emails_ativos() -> list[str]:
    emails = {a["email"] for a in listar_ativos()}
    emails.add(ADMIN_EMAIL.lower().strip())
    return sorted(e for e in emails if e)


def regenerar_ngrok_yml() -> Path:
    """Reescreve ngrok.yml preservando authtoken + domain, atualizando allow_emails."""
    if not NGROK_YML.exists():
        raise FileNotFoundError(f"ngrok.yml não encontrado em {NGROK_YML}")

    cfg = yaml.safe_load(NGROK_YML.read_text()) or {}
    tunnels = cfg.setdefault("tunnels", {})
    tun = tunnels.setdefault(NGROK_TUNNEL_NAME, {})
    oauth = tun.setdefault("oauth", {"provider": "google"})
    oauth["allow_emails"] = _emails_ativos()

    NGROK_YML.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    log.info("ngrok.yml regenerado com %d e-mails", len(oauth["allow_emails"]))
    return NGROK_YML


def reload_ngrok() -> bool:
    """Reinicia o ngrok via launchctl (se instalado) ou mata o processo pra respawn."""
    label = "com.ngrok.dashboard"
    try:
        r = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            check=False, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            log.info("ngrok reiniciado via launchctl")
            return True
    except FileNotFoundError:
        pass

    # fallback: matar o processo (ele volta se tiver KeepAlive, ou será manual)
    try:
        out = subprocess.check_output(["pgrep", "-f", "ngrok start"], text=True)
        for pid in out.strip().split("\n"):
            if pid:
                os.kill(int(pid), signal.SIGTERM)
        log.info("ngrok sinalizado via pgrep/SIGTERM")
        return True
    except subprocess.CalledProcessError:
        log.warning("ngrok não encontrado em execução")
        return False


# ----------------------------- processar webhook ----------------------------- #

def processar_webhook_kiwify(payload: dict) -> dict:
    """Interpreta um payload da Kiwify, atualiza DB, regenera YAML e reinicia ngrok.

    Retorna um resumo da ação tomada.
    """
    evento = (
        payload.get("webhook_event_type")
        or payload.get("event")
        or payload.get("type")
    )
    customer = payload.get("Customer") or payload.get("customer") or {}
    email = (customer.get("email") or payload.get("email") or "").strip().lower()
    nome = customer.get("full_name") or customer.get("name") or payload.get("name")
    order_id = (
        payload.get("order_id") or payload.get("transaction_id")
        or (payload.get("Order") or {}).get("id")
    )
    produto = (
        (payload.get("Product") or {}).get("product_name")
        or payload.get("product_name")
    )

    log_evento(evento, email, payload)

    if not email:
        return {"ok": False, "motivo": "sem email no payload", "evento": evento}

    if evento in EVENTOS_LIBERA:
        novo_status = "ativo"
    elif evento in EVENTOS_REMOVE:
        novo_status = "cancelado"
    else:
        return {"ok": True, "ignorado": True, "evento": evento, "email": email}

    upsert_assinante(email, nome, order_id, produto, novo_status, payload)
    try:
        regenerar_ngrok_yml()
        reload_ngrok()
    except Exception as e:
        log.exception("falha ao atualizar ngrok")
        return {"ok": True, "status": novo_status, "email": email,
                "erro_ngrok": str(e)}

    return {"ok": True, "status": novo_status, "email": email, "evento": evento}
