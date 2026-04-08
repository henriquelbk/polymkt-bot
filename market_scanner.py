"""
Polymarket Market Scanner
=========================
Busca mercados abertos no Polymarket, aplica scoring heurístico baseado no
edge histórico do usuário e recomenda posições para apostar.

Uso:
    python market_scanner.py              # scan normal, salva SCAN.md
    python market_scanner.py --analyze    # + gera prompt para colar no Claude.ai
    python market_scanner.py --top N      # mostra top N (padrão: 10)
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

from config import (
    CATEGORY_FILTER_ONLY,
    DATA_FILE,
    KELLY_CAP,
    KELLY_FRACTION,
    POLYMARKET_GAMMA_API,
    SCAN_FILE,
    USER_CATEGORIES,
    USER_EDGE_BRACKETS,
)

# ---------------------------------------------------------------------------
# Constantes de scoring
# ---------------------------------------------------------------------------

# Pontuação máxima possível antes do cap
SCORE_CAP = 100

# Win rates por bracket usados no Kelly (estimados conservadoramente)
BRACKET_WIN_RATES = {
    "75-85": 0.80,
    "60-75": 0.78,
    "45-60": 0.72,
    "<45":   0.40,
}

# Palavras-chave nos títulos dos mercados para detectar football-europe
FOOTBALL_EUROPE_KEYWORDS = [
    # Competições
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "champions league", "europa league", "conference league",
    "fa cup", "copa del rey", "dfb pokal", "coppa italia", "coupe de france",
    "nations league", "euro 2024", "euro 2025", "euro 2026",
    "world cup", "copa do mundo",
    "uefa",
    # Seleções
    "england", "spain", "germany", "france", "italy", "portugal",
    "netherlands", "belgium", "croatia", "austria", "switzerland",
    # Clubes ingleses
    "arsenal", "chelsea", "liverpool", "manchester city", "manchester united",
    "tottenham", "newcastle", "aston villa", "brighton", "west ham",
    # Clubes espanhóis
    "barcelona", "real madrid", "atletico madrid", "atletico",
    "sevilla", "valencia", "villarreal", "real betis", "athletic bilbao",
    "getafe", "celta vigo", "osasuna", "girona", "alaves", "mallorca",
    "real sociedad", "espanyol", "valladolid",
    # Clubes alemães
    "bayern", "dortmund", "bayer leverkusen", "rb leipzig", "eintracht",
    "wolfsburg", "freiburg", "hoffenheim", "mainz", "borussia",
    # Clubes italianos
    "juventus", "ac milan", "inter milan", "napoli", "as roma", "lazio",
    "fiorentina", "atalanta", "torino", "bologna",
    # Clubes franceses
    "psg", "paris saint-germain", "marseille", "lyon", "monaco", "lille", "nice",
    # Clubes portugueses
    "benfica", "sporting cp", "sporting lisbon", "porto", "braga",
]


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_markets(limit: int = 500) -> list[dict]:
    """Busca mercados ativos na gamma-api do Polymarket, ordenados por data de fechamento."""
    all_markets: list[dict] = []

    # Primeiro batch: ordenado por endDate ascendente (fecha mais cedo = mais relevante)
    for order, ascending in [("endDate", "true"), ("volume", "false")]:
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": 0,
            "order": order,
            "ascending": ascending,
        }
        try:
            resp = requests.get(POLYMARKET_GAMMA_API, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                all_markets.extend(data)
            elif isinstance(data, dict) and "data" in data:
                all_markets.extend(data["data"])
        except requests.RequestException as e:
            print(f"Aviso: erro ao buscar batch ({order}): {e}", file=sys.stderr)

    # Deduplica por id
    seen: set[str] = set()
    unique: list[dict] = []
    for m in all_markets:
        mid = m.get("conditionId") or m.get("id", "")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)

    return unique


def load_open_positions() -> set[str]:
    """Retorna conjunto de market_ids já na carteira do usuário."""
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {
            b["market_id"]
            for b in data.get("bets", [])
            if not b.get("is_closed", True)
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return set()


# ---------------------------------------------------------------------------
# Helpers de tempo e preço
# ---------------------------------------------------------------------------

def parse_end_date(market: dict) -> datetime | None:
    """Extrai a data de fechamento do mercado (vários formatos possíveis)."""
    for field in ("endDate", "end_date", "endDateIso", "closeTime"):
        raw = market.get(field)
        if raw:
            try:
                # Remove Z e converte
                raw = str(raw).replace("Z", "+00:00")
                return datetime.fromisoformat(raw)
            except ValueError:
                pass
    return None


def hours_until_close(end_dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    delta = end_dt - now
    return delta.total_seconds() / 3600


def format_closes_in(hours: float) -> str:
    if hours < 1:
        return f"{int(hours * 60)}min"
    if hours < 24:
        return f"{hours:.0f}h"
    days = hours / 24
    if days < 2:
        return f"1d {hours % 24:.0f}h"
    return f"{days:.0f}d"


def get_outcome_prices(market: dict) -> list[float]:
    """Retorna lista de preços dos outcomes (0.0 a 1.0)."""
    raw = market.get("outcomePrices")
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    try:
        return [float(p) for p in raw]
    except (TypeError, ValueError):
        return []


def get_outcomes(market: dict) -> list[str]:
    """Retorna nomes dos outcomes."""
    raw = market.get("outcomes")
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    return [str(o) for o in raw]


def get_volume(market: dict) -> float:
    for field in ("volume", "volumeNum", "volume24hr"):
        v = market.get(field)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


# ---------------------------------------------------------------------------
# Filtro e detecção de categoria
# ---------------------------------------------------------------------------

def is_football_europe(market: dict) -> bool:
    text = (market.get("question", "") + " " + market.get("slug", "")).lower()
    tags = [t.get("slug", "") + " " + t.get("label", "") for t in (market.get("tags") or [])]
    tag_text = " ".join(tags).lower()
    combined = text + " " + tag_text
    return any(kw in combined for kw in FOOTBALL_EUROPE_KEYWORDS)


def detect_categories(market: dict) -> list[str]:
    cats = []
    if is_football_europe(market):
        cats.append("football-europe")
    return cats


def get_price_bracket(price: float) -> str:
    if price >= 0.75:
        return "75-85"
    if price >= 0.60:
        return "60-75"
    if price >= 0.45:
        return "45-60"
    return "<45"


def filter_candidates(markets: list[dict], open_ids: set[str]) -> list[dict]:
    """Elimina mercados inviáveis antes do scoring."""
    valid = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=45)

    for m in markets:
        # Já na carteira
        cid = m.get("conditionId") or m.get("condition_id") or m.get("id", "")
        if cid in open_ids:
            continue

        # Sem preços válidos
        prices = get_outcome_prices(m)
        if not prices or all(p == 0 for p in prices):
            continue

        # Nenhum outcome em range útil (exclui mercados já praticamente resolvidos)
        if not any(0.10 <= p <= 0.95 for p in prices):
            continue

        # Volume mínimo
        if get_volume(m) < 1000:
            continue

        # Data de fechamento
        end_dt = parse_end_date(m)
        if end_dt is None:
            continue
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if end_dt > cutoff:
            continue
        if end_dt <= now:
            continue

        # Filtro por categoria (se ativado)
        if CATEGORY_FILTER_ONLY:
            if not any(cat in USER_CATEGORIES for cat in detect_categories(m)):
                continue

        valid.append(m)
    return valid


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_market(market: dict, hours: float, cats: list[str], bracket: str) -> tuple[int, list[str]]:
    """Retorna (score, lista_de_motivos)."""
    score = 0
    reasons = []

    # Near-resolution
    if 24 <= hours <= 72:
        score += 35
        reasons.append("near-resolution (24-72h)")
    elif hours < 24:
        score += 25
        score -= 10  # risco adicional
        reasons.append("very near-resolution (<24h, risco alto)")
    elif hours <= 168:  # até 7 dias
        score += 20
        reasons.append("resolucao proxima (3-7d)")

    # Categoria preferida
    for cat in cats:
        if cat in USER_CATEGORIES:
            score += 25
            reasons.append(f"categoria especialista: {cat}")

    # Bracket de preço
    edge = USER_EDGE_BRACKETS.get(bracket, 0)
    if bracket == "60-75":
        score += 25
        reasons.append(f"bracket 60-75% (edge hist: +{edge:.1f}%)")
    elif bracket == "45-60":
        score += 20
        reasons.append(f"bracket 45-60% (edge hist: +{edge:.1f}%)")
    elif bracket == "75-85":
        score += 15
        reasons.append(f"bracket 75-85% (edge hist: +{edge:.1f}%)")
    elif bracket == "<45":
        score -= 15
        reasons.append(f"underdog <45% (edge hist: {edge:.1f}% — evitar)")

    # Volume / liquidez
    vol = get_volume(market)
    if vol >= 50_000:
        score += 10
        reasons.append(f"alto volume (${vol:,.0f})")
    elif vol >= 10_000:
        score += 5

    return min(score, SCORE_CAP), reasons


# ---------------------------------------------------------------------------
# Kelly Criterion
# ---------------------------------------------------------------------------

def kelly_size(price: float, bracket: str) -> float:
    """Retorna fração do bankroll (1/KELLY_FRACTION Kelly, cap KELLY_CAP)."""
    wr = BRACKET_WIN_RATES.get(bracket, 0.5)
    if price <= 0 or price >= 1:
        return 0.0
    odds = 1.0 / price
    f_star = (wr * odds - (1 - wr)) / odds
    fractional_kelly = f_star / KELLY_FRACTION
    return max(0.0, min(fractional_kelly, KELLY_CAP))


# ---------------------------------------------------------------------------
# Build recommendations
# ---------------------------------------------------------------------------

def build_recommendations(markets: list[dict]) -> list[dict]:
    recs = []
    for m in markets:
        prices = get_outcome_prices(m)
        outcomes = get_outcomes(m)
        end_dt = parse_end_date(m)
        hours = hours_until_close(end_dt)
        cats = detect_categories(m)

            # Escolhe o outcome com melhor score em range útil (0.10-0.95)
        best_idx = 0
        best_score = -999
        for i, p in enumerate(prices):
            if not (0.10 <= p <= 0.95):
                continue
            bracket = get_price_bracket(p)
            s, _ = score_market(m, hours, cats, bracket)
            # Penaliza underdogs
            if bracket == "<45":
                s -= 20
            if s > best_score:
                best_score = s
                best_idx = i

        price = prices[best_idx] if best_idx < len(prices) else 0.5
        outcome_name = outcomes[best_idx] if best_idx < len(outcomes) else "Yes"
        bracket = get_price_bracket(price)
        score, reasons = score_market(m, hours, cats, bracket)
        kelly = kelly_size(price, bracket)

        recs.append({
            "title": m.get("question", "?"),
            "outcome": outcome_name,
            "price": round(price, 4),
            "closes_in": format_closes_in(hours),
            "end_dt": end_dt.strftime("%Y-%m-%d %H:%M UTC") if end_dt else "?",
            "volume": get_volume(m),
            "score": score,
            "kelly_pct": round(kelly * 100, 1),
            "bracket": bracket,
            "categories": cats,
            "reasons": reasons,
            "market_id": m.get("conditionId") or m.get("id", ""),
        })

    recs.sort(key=lambda r: r["score"], reverse=True)
    return recs


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_recommendations(recs: list[dict], top: int = 10) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\nPolymarket Scanner -- {today}")
    print("=" * 48)
    print(f"Top {min(top, len(recs))} oportunidades:\n")

    for i, r in enumerate(recs[:top], 1):
        cats_str = ", ".join(r["categories"]) if r["categories"] else "geral"
        reasons_str = " + ".join(r["reasons"])
        vol_str = f"${r['volume']:,.0f}" if r["volume"] > 0 else "?"
        print(f"[{r['score']:2d}] {r['title'][:65]}")
        print(f"     Outcome: {r['outcome']} | Preco: {r['price']:.2f} | Fecha: {r['closes_in']} | Vol: {vol_str}")
        print(f"     Edge: {reasons_str}")
        print(f"     Kelly sugerido: {r['kelly_pct']:.1f}% do bankroll")
        print()


def save_scan_md(recs: list[dict], top: int = 10, path: str = SCAN_FILE) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Polymarket Scan -- {today}",
        "",
        "## Top Oportunidades",
        "",
        "| # | Mercado | Outcome | Preco | Fecha | Score | Kelly |",
        "|---|---------|---------|-------|-------|-------|-------|",
    ]
    for i, r in enumerate(recs[:top], 1):
        title = r["title"][:50] + ("..." if len(r["title"]) > 50 else "")
        lines.append(
            f"| {i} | {title} | {r['outcome']} | {r['price']:.2f} | {r['closes_in']} "
            f"| {r['score']} | {r['kelly_pct']:.1f}% |"
        )

    lines += ["", "---", "", "## Detalhes", ""]

    for i, r in enumerate(recs[:top], 1):
        cats_str = ", ".join(r["categories"]) if r["categories"] else "geral"
        reasons_str = "\n  - ".join(r["reasons"])
        edge_str = USER_EDGE_BRACKETS.get(r["bracket"], "n/a")
        lines += [
            f"### [{r['score']}] {r['title']}",
            f"- **Outcome**: {r['outcome']} | **Preco**: {r['price']:.2f} | **Fecha**: {r['end_dt']}",
            f"- **Volume**: ${r['volume']:,.0f} | **Categoria**: {cats_str}",
            f"- **Motivos**:",
            f"  - {reasons_str}",
            f"- **Edge historico bracket {r['bracket']}%**: {edge_str}%",
            f"- **Kelly sizing**: {r['kelly_pct']:.1f}% (1/{KELLY_FRACTION} Kelly, cap {KELLY_CAP*100:.0f}%)",
            "",
        ]

    lines += [
        "---",
        "",
        f"*Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"SCAN.md salvo em {path}")


def generate_analyze_prompt(recs: list[dict], top: int = 10) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"Hoje e {today}. Abaixo estao os top mercados do Polymarket identificados por heuristicas.",
        "Para cada um, avalie: o preco de mercado parece justo? Ha edge real aqui?",
        "Considere base rates historicos, noticias recentes, e probabilidade real vs. mercado.",
        "",
    ]
    for i, r in enumerate(recs[:top], 1):
        lines.append(
            f"{i}. {r['title']} | Outcome: {r['outcome']} | Preco atual: {r['price']:.2f} "
            f"| Fecha: {r['closes_in']}"
        )
    lines += [
        "",
        "Para cada mercado: (a) probabilidade que voce estimaria, (b) edge vs. mercado em pp, "
        "(c) recomendacao: apostar / pular / monitorar.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    analyze = "--analyze" in args
    top = 10
    if "--top" in args:
        idx = args.index("--top")
        try:
            top = int(args[idx + 1])
        except (IndexError, ValueError):
            pass

    print("Buscando mercados...", end=" ", flush=True)
    markets = fetch_markets(limit=500)
    print(f"{len(markets)} encontrados.")

    open_ids = load_open_positions()
    candidates = filter_candidates(markets, open_ids)
    print(f"Candidatos apos filtro: {len(candidates)}")

    if not candidates:
        print("Nenhum candidato viavel encontrado.")
        return

    recs = build_recommendations(candidates)
    print_recommendations(recs, top=top)
    save_scan_md(recs, top=top)

    if analyze:
        print("\n" + "=" * 48)
        print("PROMPT PARA CLAUDE.AI (cole em claude.ai/chat):")
        print("=" * 48)
        print(generate_analyze_prompt(recs, top=top))


if __name__ == "__main__":
    main()
