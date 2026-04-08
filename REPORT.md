# Polymarket Bet Tracker — Relatório Estratégico

> Atualizado em: **2026-04-08 21:11 UTC**

---

## Resumo Geral

| Métrica | Valor |
|---------|-------|
| Total de apostas | 22 |
| Apostas fechadas | 12 (9W / 3L) |
| Apostas abertas  | 10 |
| Win rate         | 75.0% |
| Total investido  | $78.31 |
| Valor aberto atual | $627.80 |
| Total resgatado  | $31.06 |
| P&L realizado    | $+3.36 |
| ROI (fechado)    | +4.29% |
| **Edge médio vs mercado** | `+8.65%` (n=10) |

## Você está +1% acima do mercado?

✅ **SIM** — edge médio acima de +1%. Estratégia está funcionando.

> **Edge vs mercado** = preço de resolução − preço médio pago.
> Meta: ≥ +1% em média ao longo de 50+ apostas resolvidas.
> Com 10 amostras, os dados são indicativos mas ainda com alta variância.

## Edge por Faixa de Preço de Mercado

> Onde você realmente tem vantagem?

| Faixa | Apostas | Win rate | Edge médio | Recomendação |
|-------|---------|----------|------------|-------------|
| ≥ 75% (favorito claro) | 2 | 100% | +22.5% | ✅ Aposte |
| 60–75% (favorito moderado) | 5 | 80% | +15.3% | ✅ Aposte |
| 45–60% (equilibrado) | 1 | 100% | +49.2% | ✅ Aposte |
| < 45% (azarão) | 4 | 50% | -42.0% | ❌ Evite |

> **Regra derivada dos seus dados:** só aposte em faixas com edge médio > +5%.

## Calibração

_Sem dados de estimativa pessoal ainda. Use `python log_bet.py` para registrar sua probabilidade estimada a cada aposta._

## Sizing Recomendado (Kelly Criterion)

Com base no seu histórico (win rate 75.0%, edge médio +8.65%):

| 1/4 Kelly (conservador) | Recomendação |
|------------------------|--------------|
| **12.0% do bankroll** | Máximo por aposta com edge confirmado |

> Exemplo: se seu bankroll é $100, aposte no máximo **$12.00 por mercado** onde tem edge claro.
> Cap aplicado em 12% para proteger contra superestimação de edge com amostra pequena (10 apostas).
> Aumente o tamanho gradualmente conforme confirma o edge (meta: 50+ apostas resolvidas).

## Performance por Categoria

_Nenhum metadado registrado ainda. Use `python log_bet.py` antes de cada aposta._

---

## Apostas Abertas

| Mercado | Preço pago | Investido | Valor atual | PnL não realizado |
|---------|-----------|-----------|-------------|-------------------|
| Will Portugal win the 2026 FIFA World Cup? | 0.07 | $3.99 | $220.59 | +216.59 |
| Will France win the 2026 FIFA World Cup? | 0.14 | $4.00 | $119.81 | +115.81 |
| Will Spain win the 2026 FIFA World Cup? | 0.16 | $4.00 | $99.36 | +95.36 |
| Will GTA 6 cost $100+? | 0.86 | $8.00 | $74.44 | +66.44 |
| Will Neymar play in the 2026 FIFA World Cup? | 0.64 | $4.00 | $27.34 | +23.34 |
| Arsenal FC vs. Sporting CP: O/U 2.5 | 0.56 | $3.95 | $26.58 | +22.63 |
| Will Arsenal FC win on 2026-04-15? | 0.71 | $3.97 | $21.99 | +18.02 |
| FC Barcelona vs. Club Atlético de Madrid: O/U | 0.86 | $3.98 | $21.44 | +17.46 |
| Will Luiz Inácio Lula da Silva win the 2026 B | 0.57 | $3.00 | $16.23 | +13.23 |
| FC Barcelona vs. Club Atlético de Madrid: O/U | 0.64 | $3.96 | $0.02 | -3.94 |

---

## Histórico Fechado

| | Mercado | Preço pago | Investido | PnL ($) | PnL (%) | Edge |
|-|---------|-----------|-----------|---------|---------|------|
| ✅ | Liverpool FC leading at halftime? | 0.60 | $3.00 | +2.00 | +66.7% | +40.0% |
| ✅ | SC Corinthians Paulista vs. CR Flamengo: | 0.67 | $4.00 | +1.97 | +49.2% | +33.0% |
| ✅ | Will Liverpool FC win on 2026-03-18? | 0.51 | $1.97 | +1.90 | +96.9% | +49.2% |
| ✅ | Counter-Strike: NRG vs FURIA (BO3) - BLA | 0.77 | $4.00 | +1.19 | +29.9% | +23.0% |
| ✅ | Counter-Strike: TYLOO vs Team Falcons (B | 0.78 | $4.00 | +1.13 | +28.2% | +22.0% |
| ✅ | Will FC Barcelona win on 2026-03-18? | 0.64 | $2.00 | +1.12 | +56.2% | +36.0% |
| ✅ | Will George Russell be the 2026 F1 Drive | 0.00 | $4.00 | +0.97 | +24.3% | — |
| ✅ | Will FC Bayern München win on 2026-03-18 | 0.72 | $2.00 | +0.78 | +38.9% | +28.0% |
| ✅ | Iran x Israel/US conflict ends by June 3 | 0.00 | $2.50 | +0.29 | +11.5% | — |
| ❌ | Will SE Palmeiras win on 2026-03-12? | 0.42 | $2.00 | -2.00 | -100.0% | -42.0% |
| ❌ | Will Andrea Kimi Antonelli finish on the | 0.42 | $2.00 | -2.00 | -100.0% | -42.0% |
| ❌ | Will FC Bayern München win on 2026-04-07 | 0.61 | $4.00 | -4.00 | -100.0% | -60.7% |

---
*Gerado por tracker.py — registre apostas com `python log_bet.py`*
