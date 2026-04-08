"""
Configuração do tracker.
Edite WALLET_ADDRESS com o seu endereço Polymarket (Polygon wallet).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Seu endereço de carteira Polygon conectado ao Polymarket
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# URLs da API pública do Polymarket
POLYMARKET_ACTIVITY_API = "https://data-api.polymarket.com/activity"
POLYMARKET_POSITIONS_API = "https://data-api.polymarket.com/positions"
POLYMARKET_GAMMA_API    = "https://gamma-api.polymarket.com/markets"

# Arquivos onde os dados ficam salvos
DATA_FILE   = "data/bets.json"
META_FILE   = "data/bets_meta.json"
REPORT_FILE = "REPORT.md"
SCAN_FILE   = "SCAN.md"

# Categorias onde o usuário tem edge comprovado (calibrar conforme experiência)
USER_CATEGORIES = ["football-europe"]

# Se True, o scanner só recomenda mercados das categorias em USER_CATEGORIES
CATEGORY_FILTER_ONLY = True

# Sizing do bankroll: fração do Kelly a usar e cap máximo por aposta
# Ajustar KELLY_CAP durante fase de teste (ex: 0.03 = 3%)
KELLY_FRACTION = 4    # divide o Kelly completo por esse número (4 = 1/4 Kelly)
KELLY_CAP      = 0.03  # cap máximo por aposta (3% para fase de teste)

# Edge histórico por bracket de preço (atualizado automaticamente pelo tracker.py via bets.json)
# Valores padrão baseados nos dados atuais — o scanner lê do bets.json em runtime
USER_EDGE_BRACKETS = {
    "75-85": +22.5,
    "60-75": +34.2,
    "45-60": +49.2,
    "<45":   -42.0,  # underdogs: evitar
}

# --- Copy-trade ---
# Endereço Polygon do trader a monitorar (@swisstony no Polymarket)
COPY_TRADER_ADDRESS = "0x204f72f35326db932158cba6adff0b9a1da95e14"

# Janela de atividade recente a considerar (em horas)
COPY_LOOKBACK_HOURS = 48

# Arquivo de saída do copy scanner
COPY_FILE = "COPY.md"
