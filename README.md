# Polymarket Bet Tracker

Rastreia todas as suas apostas no Polymarket, calcula edge vs. mercado e gera um relatório estratégico com análise de calibração, sizing por Kelly Criterion e breakdown por faixa de preço.

## Como funciona

```
# Antes de cada aposta:
python log_bet.py      → registra sua estimativa de probabilidade + raciocínio

# Quando quiser atualizar:
python tracker.py      → busca API, reconstrói histórico → data/bets.json + REPORT.md
```

O tracker busca tanto posições abertas (`/positions`) quanto o histórico completo de atividade (`/activity`), reconstruindo apostas já fechadas ou resgatadas que a API de posições não retorna.

## Setup

### 1. Clone e instale dependências

```bash
git clone https://github.com/henriquelbk/polymkt-bot.git
cd polymkt-bot
pip install -r requirements.txt
```

### 2. Configure seu endereço

```bash
cp .env.example .env
# Edite .env e coloque seu endereço Polygon (o mesmo conectado ao Polymarket)
```

### 3. Rode

```bash
# Atualizar dados e relatório:
python tracker.py

# Registrar uma aposta antes de executar no site:
python log_bet.py
```

### 4. GitHub Actions (opcional)

Para rodar manualmente pelo GitHub sem precisar estar no computador:

1. Crie o repositório no GitHub
2. Vá em **Settings → Secrets and variables → Actions**
3. Adicione o secret `WALLET_ADDRESS` com seu endereço Polygon
4. Push do código
5. Dispare manualmente em **Actions → Update Bet Tracker → Run workflow**

## Fluxo de uso

```
1. Você vê uma aposta interessante no Polymarket
2. python log_bet.py        ← registra sua estimativa ANTES de clicar
3. Executa a aposta no site
4. python tracker.py        ← sincroniza e atualiza REPORT.md
```

O passo 2 é o mais importante: sem registrar sua estimativa de probabilidade antes, não é possível saber se você tem edge real ou está apenas acompanhando favoritos.

## Arquivos gerados

| Arquivo | Conteúdo |
|---------|----------|
| `data/bets.json` | Todas as apostas em JSON (histórico completo) |
| `data/bets_meta.json` | Metadados registrados via `log_bet.py` (estimativas, categorias, raciocínio) |
| `REPORT.md` | Relatório estratégico completo |

## O que o relatório mostra

- **Resumo geral:** win rate, P&L, ROI, edge médio vs. mercado
- **Edge por faixa de preço:** onde você realmente tem vantagem (favoritos vs. azarões)
- **Calibração:** quando você estima 70%, você está certo 70% das vezes?
- **Kelly Criterion:** sizing recomendado por aposta com base no seu edge histórico (cap 12%)
- **Performance por categoria:** breakdown por tipo de mercado (futebol, CS2, política, etc.)
- **Apostas abertas:** valor atual vs. investido
- **Histórico fechado:** PnL e edge realizado por aposta

## Estrutura

```
polymkt-bot/
├── tracker.py              # Busca API, reconstrói histórico, gera relatório
├── log_bet.py              # Registra estimativa + raciocínio antes da aposta
├── config.py               # Configurações e URLs de API
├── STRATEGY.md             # Framework de edge: 5 alavancas comprovadas
├── REPORT.md               # Relatório gerado pelo tracker
├── data/
│   ├── bets.json           # Histórico completo de apostas
│   └── bets_meta.json      # Metadados de cada aposta (via log_bet.py)
├── .github/
│   └── workflows/
│       └── update.yml      # GitHub Actions (disparo manual)
├── requirements.txt
└── .env.example
```
