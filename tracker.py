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
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from config import (
    DATA_FILE,
    META_FILE,
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


def reconstruct_closed_bets(activity: list[dict], open_ids: set[str]) -> list[dict]:
    """Reconstrói apostas fechadas/vendidas a partir do histórico de atividade.

    A API de posições só retorna posições abertas. Mercados já resolvidos ou
    posições vendidas só aparecem no endpoint de atividade, então precisamos
    reconstruí-los manualmente a partir dos eventos TRADE e REDEEM.
    """
    from collections import defaultdict

    markets: dict[str, dict] = defaultdict(lambda: {
        "title": "N/A", "trades": [], "redeems": []
    })

    for ev in activity:
        cid = ev.get("conditionId", "")
        if not cid:
            continue
        ev_type = ev.get("type", "")
        if ev_type == "TRADE":
            markets[cid]["trades"].append(ev)
            if not markets[cid]["title"] or markets[cid]["title"] == "N/A":
                markets[cid]["title"] = ev.get("title", "N/A")
        elif ev_type == "REDEEM":
            markets[cid]["redeems"].append(ev)
            if not markets[cid]["title"] or markets[cid]["title"] == "N/A":
                markets[cid]["title"] = ev.get("title", "N/A")

    now = datetime.now(timezone.utc).isoformat()
    closed_bets = []

    for cid, data in markets.items():
        if cid in open_ids:
            continue  # já está na lista de posições abertas

        trades = data["trades"]
        redeems = data["redeems"]

        if not trades:
            continue

        buy_trades  = [t for t in trades if t.get("side") == "BUY"]
        sell_trades = [t for t in trades if t.get("side") == "SELL"]

        buy_usdc  = sum(t.get("usdcSize", 0) for t in buy_trades)
        sell_usdc = sum(t.get("usdcSize", 0) for t in sell_trades)
        buy_size  = sum(t.get("size", 0) for t in buy_trades)
        sell_size = sum(t.get("size", 0) for t in sell_trades)

        redeem_usdc = sum(r.get("usdcSize", 0) for r in redeems)

        # Contratos líquidos que chegaram à resolução (comprados - vendidos)
        net_size = max(buy_size - sell_size, 0.0)
        # Investimento líquido (desconta o que foi recebido nas vendas parciais)
        net_invested = max(buy_usdc - sell_usdc, 0.0)

        avg_price = (net_invested / net_size) if net_size > 0.001 else (
            buy_usdc / buy_size if buy_size > 0 else 0.0
        )

        is_redeemed   = len(redeems) > 0
        is_fully_sold = sell_size >= buy_size * 0.99
        is_closed     = is_redeemed or is_fully_sold

        # PnL e base de cálculo dependem do tipo de fechamento
        if is_fully_sold and not is_redeemed:
            # Posição vendida manualmente: custo base é o total comprado
            report_initial = buy_usdc
            pnl_dollar     = sell_usdc - buy_usdc
        else:
            # Posição resolvida pelo mercado (REDEEM), possivelmente com venda parcial
            report_initial = net_invested
            pnl_dollar     = redeem_usdc - net_invested

        pnl_pct = (pnl_dollar / report_initial * 100) if report_initial > 0.001 else 0.0

        # Edge: só calculável quando há resolução pelo mercado (REDEEM)
        edge_vs_market: float | None = None
        if is_redeemed and net_size > 0.001:
            resolved_price_per = redeem_usdc / net_size
            edge_vs_market = round((resolved_price_per - avg_price) * 100, 2)

        # Outcome do bet (usa o último BUY como referência)
        last_buy = buy_trades[-1] if buy_trades else {}
        outcome_index = str(last_buy.get("outcomeIndex", "N/A"))
        outcome_name  = last_buy.get("outcome") or outcome_index

        current_price = (redeem_usdc / net_size) if (is_redeemed and net_size > 0.001) else avg_price

        closed_bets.append({
            "market_id":      cid,
            "title":          data["title"],
            "outcome":        outcome_index,
            "size":           round(net_size, 4),
            "avg_price":      round(avg_price, 4),
            "current_price":  round(current_price, 4),
            "initial_value":  round(report_initial, 4),
            "current_value":  round(redeem_usdc if is_redeemed else sell_usdc, 4),
            "redeemed_value": round(redeem_usdc, 4),
            "pnl_dollar":     round(pnl_dollar, 4),
            "pnl_pct":        round(pnl_pct, 2),
            "is_closed":      is_closed,
            "edge_vs_market": edge_vs_market,
            "fetched_at":     now,
        })

    return closed_bets


# ---------------------------------------------------------------------------
# Metadata (bets_meta.json — registrado via log_bet.py)
# ---------------------------------------------------------------------------

def load_meta(path: str) -> list[dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("entries", [])
    return []


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

def compute_stats(bets: list[dict], meta: list[dict]) -> dict[str, Any]:
    closed = [b for b in bets if b["is_closed"]]
    open_  = [b for b in bets if not b["is_closed"]]

    total_invested    = sum(b["initial_value"] for b in bets)
    total_open_value  = sum(b["current_value"] for b in open_)
    total_redeemed    = sum(b["redeemed_value"] for b in closed)
    total_pnl         = sum(b["pnl_dollar"] for b in closed)
    roi_closed        = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    edges     = [b["edge_vs_market"] for b in closed if b["edge_vs_market"] is not None]
    avg_edge  = sum(edges) / len(edges) if edges else None

    wins   = [b for b in closed if b["pnl_dollar"] > 0]
    losses = [b for b in closed if b["pnl_dollar"] <= 0]

    # --- Análise por faixa de preço de mercado ---
    brackets = [
        ("≥ 75% (favorito claro)",    0.75, 1.01),
        ("60–75% (favorito moderado)", 0.60, 0.75),
        ("45–60% (equilibrado)",       0.45, 0.60),
        ("< 45% (azarão)",             0.00, 0.45),
    ]
    bracket_stats = []
    for label, lo, hi in brackets:
        group = [b for b in closed if lo <= b["avg_price"] < hi]
        if not group:
            continue
        g_wins  = [b for b in group if b["pnl_dollar"] > 0]
        g_edges = [b["edge_vs_market"] for b in group if b["edge_vs_market"] is not None]
        bracket_stats.append({
            "label":    label,
            "n":        len(group),
            "win_rate": round(len(g_wins) / len(group) * 100, 0),
            "avg_edge": round(sum(g_edges) / len(g_edges), 1) if g_edges else None,
        })

    # --- Análise por categoria (via bets_meta.json) ---
    cat_stats: dict[str, dict] = defaultdict(lambda: {"wins": 0, "total": 0, "edges": []})
    meta_by_title = {m["title"].lower(): m for m in meta}
    for b in closed:
        m = meta_by_title.get(b["title"].lower())
        if not m:
            continue
        cat = m.get("category", "other")
        cat_stats[cat]["total"] += 1
        if b["pnl_dollar"] > 0:
            cat_stats[cat]["wins"] += 1
        if b["edge_vs_market"] is not None:
            cat_stats[cat]["edges"].append(b["edge_vs_market"])

    category_rows = []
    for cat, s in sorted(cat_stats.items()):
        wr = round(s["wins"] / s["total"] * 100, 0) if s["total"] else 0
        ae = round(sum(s["edges"]) / len(s["edges"]), 1) if s["edges"] else None
        category_rows.append({"category": cat, "n": s["total"], "win_rate": wr, "avg_edge": ae})

    # --- Calibração (sua probabilidade vs resultado real) ---
    calibration_rows = []
    if meta:
        cal_buckets = defaultdict(lambda: {"n": 0, "wins": 0})
        for m in meta:
            title_lower = m["title"].lower()
            matched = next(
                (b for b in closed if b["title"].lower() == title_lower), None
            )
            if not matched or m.get("your_prob") is None:
                continue
            yp = m["your_prob"]
            bucket = round(yp * 10) * 10  # arredonda para decil (0, 10, 20…)
            cal_buckets[bucket]["n"] += 1
            if matched["pnl_dollar"] > 0:
                cal_buckets[bucket]["wins"] += 1
        for bucket in sorted(cal_buckets):
            s = cal_buckets[bucket]
            actual = round(s["wins"] / s["n"] * 100, 0) if s["n"] else 0
            calibration_rows.append({
                "your_prob": bucket,
                "n":         s["n"],
                "actual":    actual,
                "delta":     actual - bucket,
            })

    # --- Kelly recommendation baseado em edge histórico ---
    kelly_pct: float | None = None
    if avg_edge is not None and avg_edge > 0 and closed:
        # Estima o preço médio pago como proxy para as odds
        avg_price_closed = sum(b["avg_price"] for b in closed if b["avg_price"] > 0) / max(len(closed), 1)
        b_odds = (1 / avg_price_closed) - 1 if avg_price_closed > 0 else 1
        # edge_vs_market em % = (resolved_price - avg_price)*100; resolved~1.0 para wins
        # Aproxima win rate implícita pelo ROI
        wr_decimal = len(wins) / len(closed) if closed else 0
        kelly_full = (wr_decimal * b_odds - (1 - wr_decimal)) / b_odds
        kelly_pct  = round(min(max(kelly_full * 25, 0), 0.12) * 100, 1)  # 1/4 Kelly, cap 12%

    return {
        "total_bets":       len(bets),
        "closed_bets":      len(closed),
        "open_bets":        len(open_),
        "wins":             len(wins),
        "losses":           len(losses),
        "win_rate":         round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_invested":   round(total_invested, 2),
        "total_open_value": round(total_open_value, 2),
        "total_redeemed":   round(total_redeemed, 2),
        "total_pnl":        round(total_pnl, 2),
        "roi_closed_pct":   round(roi_closed, 2),
        "avg_edge_pct":     round(avg_edge, 2) if avg_edge is not None else None,
        "edge_samples":     len(edges),
        "bracket_stats":    bracket_stats,
        "category_rows":    category_rows,
        "calibration_rows": calibration_rows,
        "kelly_pct":        kelly_pct,
    }


def generate_report(bets: list[dict], stats: dict, path: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    avg_edge = stats["avg_edge_pct"]
    edge_line = (
        f"`{avg_edge:+.2f}%` (n={stats['edge_samples']})"
        if avg_edge is not None
        else "dados insuficientes (apostas resolvidas necessárias)"
    )
    if avg_edge is None or avg_edge <= 0:
        beat_verdict = "❌ **SEM EDGE** — edge negativo ou sem dados suficientes."
    elif avg_edge < 1:
        beat_verdict = "⚠️ **QUASE** — edge positivo mas abaixo de +1%. Continue coletando dados."
    else:
        beat_verdict = "✅ **SIM** — edge médio acima de +1%. Estratégia está funcionando."

    # Tabela de faixas de preço
    bracket_rows = ""
    for row in stats["bracket_stats"]:
        ae = f"{row['avg_edge']:+.1f}%" if row["avg_edge"] is not None else "—"
        verdict = "✅ Aposte" if (row["avg_edge"] or 0) > 5 else ("⚠️ Cauteloso" if (row["avg_edge"] or 0) > 0 else "❌ Evite")
        bracket_rows += f"| {row['label']} | {row['n']} | {row['win_rate']:.0f}% | {ae} | {verdict} |\n"

    bracket_section = ""
    if bracket_rows:
        bracket_section = f"""
## Edge por Faixa de Preço de Mercado

> Onde você realmente tem vantagem?

| Faixa | Apostas | Win rate | Edge médio | Recomendação |
|-------|---------|----------|------------|-------------|
{bracket_rows}
> **Regra derivada dos seus dados:** só aposte em faixas com edge médio > +5%.
"""

    # Tabela de categorias
    cat_rows = ""
    for row in stats["category_rows"]:
        ae = f"{row['avg_edge']:+.1f}%" if row["avg_edge"] is not None else "—"
        cat_rows += f"| {row['category']} | {row['n']} | {row['win_rate']:.0f}% | {ae} |\n"

    cat_section = ""
    if cat_rows:
        cat_section = f"""
## Performance por Categoria

| Categoria | Apostas | Win rate | Edge médio |
|-----------|---------|----------|------------|
{cat_rows}
> Registre suas apostas com `python log_bet.py` para popular esta tabela.
"""
    else:
        cat_section = """
## Performance por Categoria

_Nenhum metadado registrado ainda. Use `python log_bet.py` antes de cada aposta._
"""

    # Seção de calibração
    cal_section = ""
    if stats["calibration_rows"]:
        cal_rows = ""
        for row in stats["calibration_rows"]:
            delta_str = f"{row['delta']:+.0f}pp"
            signal = "✅" if abs(row["delta"]) <= 10 else ("📈 superestimando" if row["delta"] < 0 else "📉 subestimando")
            cal_rows += f"| {row['your_prob']}% | {row['n']} | {row['actual']:.0f}% | {delta_str} | {signal} |\n"
        cal_section = f"""
## Calibração — Você vs Mercado

> Quando você estima X%, você está certo X% das vezes?

| Sua estimativa | Apostas | Resultado real | Delta | Diagnóstico |
|----------------|---------|---------------|-------|-------------|
{cal_rows}
"""
    else:
        cal_section = """
## Calibração

_Sem dados de estimativa pessoal ainda. Use `python log_bet.py` para registrar sua probabilidade estimada a cada aposta._
"""

    # Kelly sizing
    kelly = stats["kelly_pct"]
    if kelly and kelly > 0:
        kelly_section = f"""
## Sizing Recomendado (Kelly Criterion)

Com base no seu histórico (win rate {stats['win_rate']}%, edge médio {avg_edge:+.2f}%):

| 1/4 Kelly (conservador) | Recomendação |
|------------------------|--------------|
| **{kelly:.1f}% do bankroll** | Máximo por aposta com edge confirmado |

> Exemplo: se seu bankroll é $100, aposte no máximo **${kelly:.2f} por mercado** onde tem edge claro.
> Cap aplicado em 12% para proteger contra superestimação de edge com amostra pequena ({stats['edge_samples']} apostas).
> Aumente o tamanho gradualmente conforme confirma o edge (meta: 50+ apostas resolvidas).
"""
    else:
        kelly_section = """
## Sizing Recomendado

_Kelly Criterion requer edge positivo confirmado. Continue coletando dados._

Por enquanto, use **5% do bankroll por aposta** como padrão conservador.
"""

    # Tabela de apostas abertas
    open_bets  = [b for b in bets if not b["is_closed"]]
    closed_bets_list = [b for b in bets if b["is_closed"]]

    open_rows = ""
    for b in sorted(open_bets, key=lambda x: x["current_value"], reverse=True):
        unreal_pnl = b["current_value"] - b["initial_value"]
        open_rows += (
            f"| {b['title'][:45]} | {b['avg_price']:.2f}"
            f" | ${b['initial_value']:.2f} | ${b['current_value']:.2f}"
            f" | {unreal_pnl:+.2f} |\n"
        )

    closed_rows = ""
    for b in sorted(closed_bets_list, key=lambda x: x["pnl_dollar"], reverse=True):
        won = "✅" if b["pnl_dollar"] > 0 else "❌"
        edge_str = f"{b['edge_vs_market']:+.1f}%" if b["edge_vs_market"] is not None else "—"
        closed_rows += (
            f"| {won} | {b['title'][:40]} | {b['avg_price']:.2f}"
            f" | ${b['initial_value']:.2f} | {b['pnl_dollar']:+.2f}"
            f" | {b['pnl_pct']:+.1f}% | {edge_str} |\n"
        )

    report = f"""# Polymarket Bet Tracker — Relatório Estratégico

> Atualizado em: **{now}**

---

## Resumo Geral

| Métrica | Valor |
|---------|-------|
| Total de apostas | {stats['total_bets']} |
| Apostas fechadas | {stats['closed_bets']} ({stats['wins']}W / {stats['losses']}L) |
| Apostas abertas  | {stats['open_bets']} |
| Win rate         | {stats['win_rate']}% |
| Total investido  | ${stats['total_invested']} |
| Valor aberto atual | ${stats['total_open_value']:.2f} |
| Total resgatado  | ${stats['total_redeemed']} |
| P&L realizado    | ${stats['total_pnl']:+.2f} |
| ROI (fechado)    | {stats['roi_closed_pct']:+.2f}% |
| **Edge médio vs mercado** | {edge_line} |

## Você está +1% acima do mercado?

{beat_verdict}

> **Edge vs mercado** = preço de resolução − preço médio pago.
> Meta: ≥ +1% em média ao longo de 50+ apostas resolvidas.
> Com {stats['edge_samples']} amostras, {"os dados são indicativos mas ainda com alta variância." if stats['edge_samples'] < 30 else "os dados já têm validade estatística razoável."}
{bracket_section}{cal_section}{kelly_section}{cat_section}
---

## Apostas Abertas

| Mercado | Preço pago | Investido | Valor atual | PnL não realizado |
|---------|-----------|-----------|-------------|-------------------|
{open_rows}
---

## Histórico Fechado

| | Mercado | Preço pago | Investido | PnL ($) | PnL (%) | Edge |
|-|---------|-----------|-----------|---------|---------|------|
{closed_rows}
---
*Gerado por tracker.py — registre apostas com `python log_bet.py`*
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not WALLET_ADDRESS:
        print("ERRO: Defina WALLET_ADDRESS no arquivo .env")
        print("      Exemplo: WALLET_ADDRESS=0xSeuEnderecoAqui")
        sys.exit(1)

    print(f"[*] Buscando posicoes para {WALLET_ADDRESS[:10]}...")
    raw_positions = fetch_positions(WALLET_ADDRESS)

    print(f"[*] Buscando historico de atividade...")
    raw_activity = fetch_activity(WALLET_ADDRESS)

    open_ids = {pos.get("conditionId", pos.get("market", "")) for pos in raw_positions}
    print(f"    {len(raw_positions)} posicoes abertas, {len(raw_activity)} eventos de atividade")

    fresh_bets   = process_positions(raw_positions)
    closed_bets  = reconstruct_closed_bets(raw_activity, open_ids)
    print(f"    {len(closed_bets)} apostas fechadas reconstruidas do historico")

    existing = load_existing(DATA_FILE)
    all_bets = merge_bets(existing, fresh_bets + closed_bets)

    if not all_bets:
        print("[!] Nenhuma aposta encontrada. Verifique o endereco.")
        return

    save_data(all_bets, DATA_FILE)
    print(f"[+] Dados salvos em {DATA_FILE}")

    meta  = load_meta(META_FILE)
    stats = compute_stats(all_bets, meta)
    generate_report(all_bets, stats, REPORT_FILE)
    print(f"[+] Relatorio gerado em {REPORT_FILE}")

    edge = stats["avg_edge_pct"]
    if edge is not None:
        symbol = "[+]" if edge >= 1 else ("[~]" if edge > 0 else "[-]")
        print(f"{symbol} Edge medio vs mercado: {edge:+.2f}%  (meta: +1.00%)")
    else:
        print("[i] Sem apostas resolvidas suficientes para calcular edge ainda.")


if __name__ == "__main__":
    main()
