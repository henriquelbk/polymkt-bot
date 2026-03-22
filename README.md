# Polymarket Bet Tracker

Rastreia automaticamente todas as suas apostas no Polymarket, calcula edge vs. mercado e gera um relatório atualizado a cada 6 horas no GitHub.

## Como funciona

```
Polymarket API ──► tracker.py ──► data/bets.json + REPORT.md ──► GitHub (auto-commit)
```

O GitHub Actions roda o tracker a cada 6 horas e faz commit automático se houver mudanças.

## Setup

### 1. Clone e instale dependências

```bash
git clone https://github.com/SEU_USUARIO/polymkt-bot.git
cd polymkt-bot
pip install -r requirements.txt
```

### 2. Configure seu endereço

```bash
cp .env.example .env
# Edite .env e coloque seu endereço Polygon (o mesmo conectado ao Polymarket)
```

### 3. Rode localmente

```bash
python tracker.py
```

Isso gera `data/bets.json` e `REPORT.md`.

### 4. Configure o GitHub Actions

1. Crie o repositório no GitHub
2. Vá em **Settings → Secrets and variables → Actions**
3. Adicione o secret `WALLET_ADDRESS` com seu endereço Polygon
4. Push do código — o workflow roda automaticamente a cada 6 horas

## Arquivos gerados

| Arquivo | Conteúdo |
|---------|----------|
| `data/bets.json` | Todas as apostas em JSON (histórico completo) |
| `REPORT.md` | Relatório legível com métricas e edge vs. mercado |

## Métricas calculadas

- Win rate
- P&L realizado e ROI
- **Edge médio vs. mercado** (principal indicador — meta: ≥ +1%)
- Número de apostas por status (aberta/fechada)

## Estratégia

Veja [STRATEGY.md](STRATEGY.md) para as 5 alavancas de edge comprovadas e o sistema de validação.

## Estrutura

```
polymkt-bot/
├── tracker.py           # Script principal
├── config.py            # Configurações e URLs de API
├── STRATEGY.md          # Estratégia para +1% de edge
├── REPORT.md            # Relatório gerado automaticamente
├── data/
│   └── bets.json        # Dados históricos de apostas
├── .github/
│   └── workflows/
│       └── update.yml   # GitHub Actions (atualiza a cada 6h)
├── requirements.txt
└── .env.example
```
