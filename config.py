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

# Arquivo onde os dados ficam salvos
DATA_FILE   = "data/bets.json"
REPORT_FILE = "REPORT.md"
