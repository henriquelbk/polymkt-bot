"""
log_bet.py — Registra uma aposta no momento da compra.

Por que isso importa:
  A única forma de saber se voce e melhor que o mercado e comparar
  SUA probabilidade estimada com o resultado real. Sem esse dado,
  voce so sabe que ganhou — nao sabe se ganhou POR RAZAO ou POR SORTE.

Uso:
  python log_bet.py

O script pergunta:
  - Titulo / URL do mercado
  - Outcome que voce comprou
  - Preco de mercado atual (0-1)
  - Sua estimativa de probabilidade real
  - Categoria e estrategia
  - Raciocinio (uma linha — forcas voce a articular por que o mercado esta errado)
  - Valor apostado em USDC
"""

import json
import os
from datetime import datetime, timezone

META_FILE = "data/bets_meta.json"

CATEGORIES = [
    "football-europe",
    "football-brazil",
    "cs2",
    "f1",
    "politics-brazil",
    "politics-us",
    "politics-other",
    "crypto",
    "pop-culture",
    "other",
]

STRATEGIES = [
    "specialist",      # edge por conhecimento de dominio
    "fade-news",       # contra-tendencia pos-noticia
    "base-rate",       # mercado ignora taxa historica
    "speed",           # arbitragem de velocidade (info nao precificada)
    "near-resolution", # mercado quase resolvido com preco ainda abaixo
    "other",
]


def load_meta() -> list[dict]:
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            return json.load(f).get("entries", [])
    return []


def save_meta(entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(META_FILE), exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def ask_float(prompt: str, lo: float = 0.0, hi: float = 1.0) -> float:
    while True:
        raw = input(f"{prompt} ({lo:.0%}–{hi:.0%}): ").strip().replace(",", ".")
        try:
            v = float(raw.strip("%")) / (100 if "%" in raw or float(raw) > 1 else 1)
            if lo <= v <= hi:
                return round(v, 4)
        except ValueError:
            pass
        print(f"  Digite um numero entre {lo} e {hi} (ex: 0.75 ou 75%)")


def ask_choice(prompt: str, options: list[str]) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("Escolha (numero): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("  Numero invalido.")


def implied_kelly(your_prob: float, market_prob: float) -> str:
    """
    Kelly Criterion: f* = (p*b - q) / b
    onde b = odds - 1 = (1/market_prob) - 1 (retorno para cada $1 apostado)
    p = sua estimativa de probabilidade
    q = 1 - p
    """
    if market_prob <= 0 or market_prob >= 1:
        return "N/A"
    b = (1 / market_prob) - 1  # retorno proporcional por contrato ganho
    p = your_prob
    q = 1 - p
    kelly = (p * b - q) / b
    if kelly <= 0:
        return "0% — SEM EDGE (nao aposte)"
    # Usar 1/4 Kelly como conservador
    full = round(kelly * 100, 1)
    quarter = round(kelly * 25, 1)
    return f"{quarter}% do bankroll (Kelly completo seria {full}% — use 1/4 Kelly)"


def main() -> None:
    print("=" * 60)
    print("  REGISTRO DE APOSTA — Polymarket Tracker")
    print("=" * 60)
    print()
    print("Preencha ANTES de executar a aposta no site.")
    print("Isso e a unica forma de medir se voce e melhor que o mercado.")
    print()

    title = ask("Titulo do mercado (ou URL)")
    if not title:
        print("Titulo obrigatorio.")
        return

    outcome = ask("Outcome que voce esta comprando (ex: Yes / No / Time X)")
    if not outcome:
        print("Outcome obrigatorio.")
        return

    market_prob = ask_float(
        "Preco atual do mercado para esse outcome",
        lo=0.01, hi=0.99,
    )
    your_prob = ask_float(
        "Sua estimativa de probabilidade REAL desse outcome",
        lo=0.01, hi=0.99,
    )

    edge_estimate = round((your_prob - market_prob) * 100, 1)
    kelly_rec = implied_kelly(your_prob, market_prob)

    print(f"\n  Edge estimado: {edge_estimate:+.1f}%")
    print(f"  Tamanho sugerido: {kelly_rec}")

    if edge_estimate <= 0:
        print("\n  AVISO: Sua estimativa nao supera o preco de mercado.")
        confirm = ask("  Continuar mesmo assim? (s/N)", "N").lower()
        if confirm != "s":
            print("  Aposta nao registrada.")
            return

    usdc = ask_float("Valor apostado (USDC)", lo=0.01, hi=100_000)
    category = ask_choice("Categoria do mercado", CATEGORIES)
    strategy = ask_choice("Estrategia usada", STRATEGIES)

    print("\nRaciocinio: em uma frase, por que o mercado esta errado?")
    rationale = ask("  (ex: Bayern em casa, adversario com 3 desfalques)")
    if not rationale:
        rationale = "(nao informado)"

    entry = {
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "outcome": outcome,
        "market_prob": market_prob,
        "your_prob": your_prob,
        "edge_estimate_pct": edge_estimate,
        "usdc_amount": usdc,
        "category": category,
        "strategy": strategy,
        "rationale": rationale,
    }

    entries = load_meta()
    entries.append(entry)
    save_meta(entries)

    print()
    print("=" * 60)
    print("  Aposta registrada com sucesso.")
    print(f"  Mercado:        {title}")
    print(f"  Outcome:        {outcome}")
    print(f"  Preco mercado:  {market_prob:.0%}")
    print(f"  Sua estimativa: {your_prob:.0%}")
    print(f"  Edge estimado:  {edge_estimate:+.1f}%")
    print(f"  Tamanho:        {kelly_rec}")
    print(f"  Categoria:      {category}")
    print(f"  Estrategia:     {strategy}")
    print(f"  Raciocinio:     {rationale}")
    print("=" * 60)
    print()
    print("Execute tracker.py apos a aposta para sincronizar com a API.")


if __name__ == "__main__":
    main()
