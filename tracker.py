"""
Polymarket Bet Tracker
======================
Busca automaticamente todas as suas apostas na API pública do Polymarket,
calcula métricas de edge vs. mercado e gera um relatório em Markdown.

Uso:
    python tracker.py

Requer:
    WALLET_ADDRESS no arquivo .env ou definido em config.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import requests

from config import (
    DATA_FILE,
    POLYMARKET_ACTIVITY_API,
    POLYMARKET_POSITIONS_API,
    REPORT_FILE,
    WALLET_ADDRESS,
)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_paginated(base_url: str, params: dict, limit: int = 500) -> list[dict]:
    """Busca todas as páginas de um endpoint com paginação por offset."""
    results = []
    params = {**params, "limit": limit, "offset": 0}
    while True:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        results.extend(page)
        if len(page) < limit:
            break
        params["offset"] += limit
    return results


def fetch_activity(address: str) -> list[dict]:
    """Retorna todas as transações (compras/vendas) do endereço."""
    return fetch_paginated(
        POLYMARKET_ACTIVITY_API,
        {"user": address},
    )


def fetch_positions(address: str) -> list[dict]:
    """Retorna posições abertas e fechadas do endereço."""
    return fetch_paginated(
        POLYMARKET_POSITIONS_API,
        {"user": address},
    )


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def parse_bet(pos: dict) -> dict:
    """Converte uma posição bruta da API em dicionário padronizado."""
    market_id    = pos.get("conditionId", pos.get("market", ""))
    title        = pos.get("title", "N/A")
    outcome      = pos.get("outcomeIndex", pos.get("outcome", "N/A"))
    outcome_name = pos.get("outcomeName", str(outcome))

    size        = float(pos.get("size", 0))          # contratos comprados
    avg_price   = float(pos.get("avgPrice", 0))       # preço médio pago (0-1)
    cur_price   = float(pos.get("currentValue", avg_price))  # valor atual por contrato
    initial_val = size * avg_price                    # USDC investido
    current_val = float(pos.get("value", size * cur_price))

    # Resultado final (se o mercado foi resolvido)
    redeemed   = float(pos.get("redeemedValue", 0))
    is_closed  = pos.get("closed", False) or redeemed > 0
    pnl_dollar = (redeemed - initial_val) if is_closed else (current_val - initial_val)
    pnl_pct    = (pnl_dollar / initial_val * 100) if initial_val > 0 else 0

    # Edge: diferença entre o preço que você pagou e o preço final de resolução
    resolved_price = float(pos.get("resolvedPrice", -1))
    edge_vs_market: float | None = None
    if resolved_price >= 0 and avg_price > 0:
        # Positivo = você comprou mais barato do que o mercado resolveu
        edge_vs_market = round((resolved_price - avg_price) * 100, 2)

    return {
        "market_id":      market_id,
        "title":          title,
        "outcome":        outcome_name,
        "size":           round(size, 4),
        "avg_price":      round(avg_price, 4),
        "current_price":  round(cur_price, 4),
        "initial_value":  round(initial_val, 4),
        "current_value":  round(current_val, 4),
        "redeemed_value": round(redeemed, 4),
        "pnl_dollar":     round(pnl_dollar, 4),
        "pnl_pct":        round(pnl_pct, 2),
        "is_closed":      is_closed,
        "edge_vs_market": edge_vs_market,
        "fetched_at":     datetime.now(timezone.utc).isoformat(),
    }


def process_positions(raw_positions: list[dict]) -> list[dict]:
    return [parse_bet(p) for p in raw_positions]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_existing(path: str) -> dict[str, dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Indexado por market_id + outcome
        return {f"{b['market_id']}_{b['outcome']}": b for b in data.get("bets", [])}
    return {}


def save_data(bets: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_bets": len(bets),
        "bets": bets,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def merge_bets(existing: dict[str, dict], fresh: list[dict]) -> list[dict]:
    """Atualiza entradas existentes e adiciona novas; preserva histórico."""
    merged = dict(existing)
    for bet in fresh:
        key = f"{bet['market_id']}_{bet['outcome']}"
        merged[key] = bet
    return list(merged.values())


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def compute_stats(bets: list[dict]) -> dict[str, Any]:
    closed = [b for b in bets if b["is_closed"]]
    open_  = [b for b in bets if not b["is_closed"]]

    total_invested = sum(b["initial_value"] for b in bets)
    total_redeemed = sum(b["redeemed_value"] for b in closed)
    total_pnl      = sum(b["pnl_dollar"] for b in closed)
    roi_closed     = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    edges = [b["edge_vs_market"] for b in closed if b["edge_vs_market"] is not None]
    avg_edge = sum(edges) / len(edges) if edges else None

    wins  = [b for b in closed if b["pnl_dollar"] > 0]
    losses= [b for b in closed if b["pnl_dollar"] <= 0]

    return {
        "total_bets":      len(bets),
        "closed_bets":     len(closed),
        "open_bets":       len(open_),
        "wins":            len(wins),
        "losses":          len(losses),
        "win_rate":        round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_invested":  round(total_invested, 2),
        "total_redeemed":  round(total_redeemed, 2),
        "total_pnl":       round(total_pnl, 2),
        "roi_closed_pct":  round(roi_closed, 2),
        "avg_edge_pct":    round(avg_edge, 2) if avg_edge is not None else None,
        "edge_samples":    len(edges),
    }


def generate_report(bets: list[dict], stats: dict, path: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    edge_line = (
        f"`{stats['avg_edge_pct']:+.2f}%` (n={stats['edge_samples']})"
        if stats["avg_edge_pct"] is not None
        else "dados insuficientes (precisa de apostas resolvidas)"
    )
    beat_market = (
        "✅ **SIM** — você está batendo o mercado em média."
        if (stats["avg_edge_pct"] or 0) >= 1
        else ("⚠️ **QUASE** — edge positivo mas abaixo de +1%." if (stats["avg_edge_pct"] or 0) > 0
              else "❌ **NÃO** — edge negativo ou sem dados suficientes.")
    )

    rows = ""
    for b in sorted(bets, key=lambda x: abs(x["pnl_dollar"]), reverse=True)[:20]:
        status = "✅ fechado" if b["is_closed"] else "🔵 aberto"
        edge_str = f"{b['edge_vs_market']:+.1f}%" if b["edge_vs_market"] is not None else "—"
        rows += (
            f"| {b['title'][:40]} | {b['outcome']} "
            f"| {b['avg_price']:.2f} | {b['initial_value']:.2f} "
            f"| {b['pnl_dollar']:+.2f} | {b['pnl_pct']:+.1f}% "
            f"| {edge_str} | {status} |\n"
        )

    report = f"""# Polymarket Bet Tracker — Relatório

> Atualizado em: **{now}**

## Resumo Geral

| Métrica | Valor |
|---------|-------|
| Total de apostas | {stats['total_bets']} |
| Apostas fechadas | {stats['closed_bets']} |
| Apostas abertas  | {stats['open_bets']} |
| Win rate         | {stats['win_rate']}% |
| Total investido  | ${stats['total_invested']} |
| Total resgatado  | ${stats['total_redeemed']} |
| P&L realizado    | ${stats['total_pnl']:+.2f} |
| ROI (fechado)    | {stats['roi_closed_pct']:+.2f}% |
| **Edge médio vs mercado** | {edge_line} |

## Você está +1% acima do mercado?

{beat_market}

> **Edge vs mercado** = preço de resolução − preço médio pago.
> Positivo significa que você comprou mais barato do que o mercado estimava no momento da resolução.
> Objetivo: média ≥ +1% ao longo de 50+ apostas.

## Top 20 Apostas (por |PnL|)

| Mercado | Outcome | Preço pago | Investido ($) | PnL ($) | PnL (%) | Edge | Status |
|---------|---------|-----------|--------------|---------|---------|------|--------|
{rows}
---
*Gerado automaticamente por [tracker.py](tracker.py)*
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not WALLET_ADDRESS:
        print("❌  Defina WALLET_ADDRESS no arquivo .env")
        print("    Exemplo: WALLET_ADDRESS=0xSeuEnderecoAqui")
        sys.exit(1)

    print(f"📡  Buscando posições para {WALLET_ADDRESS[:10]}…")
    raw = fetch_positions(WALLET_ADDRESS)
    if not raw:
        print("⚠️  Nenhuma posição encontrada. Verifique o endereço.")
        return

    print(f"   {len(raw)} posições recebidas da API")
    fresh_bets = process_positions(raw)
    existing   = load_existing(DATA_FILE)
    all_bets   = merge_bets(existing, fresh_bets)

    save_data(all_bets, DATA_FILE)
    print(f"💾  Dados salvos em {DATA_FILE}")

    stats = compute_stats(all_bets)
    generate_report(all_bets, stats, REPORT_FILE)
    print(f"📊  Relatório gerado em {REPORT_FILE}")

    edge = stats["avg_edge_pct"]
    if edge is not None:
        symbol = "✅" if edge >= 1 else ("⚠️" if edge > 0 else "❌")
        print(f"{symbol}  Edge médio vs mercado: {edge:+.2f}%  (meta: +1.00%)")
    else:
        print("ℹ️   Sem apostas resolvidas suficientes para calcular edge ainda.")


if __name__ == "__main__":
    main()
