# Estratégia para +1% Consistente no Polymarket

> Objetivo: superar o preço de mercado em média ≥ +1% por aposta resolvida.
> +1% de edge sobre centenas de apostas = retorno composto significativo.

---

## O que "edge" significa aqui

**Edge = seu preço de resolução esperado − preço que você pagou**

Exemplo: você compra "Sim" a 0.62 (62%). O mercado resolve em 1.0 (100%).
Edge = +38 pontos. Mas se o mercado já estava certo (62% de chance real),
e você paga 0.62, edge ≈ 0 no longo prazo.

Para ter edge **você precisa estar sistematicamente mais certo que o mercado**.

---

## As 5 alavancas de edge comprovadas

### 1. Especialização por categoria ("home turf")

Escolha **1 ou 2 categorias** e torne-se o expert delas:
- Crypto (on-chain data, releases, protocolos)
- Clima / desastres naturais (modelos meteorológicos)
- Eleições específicas de países/estados que você acompanha de perto
- Esportes com dados proprietários

**Por que funciona:** mercado é médio. Em categorias de nicho, quem tem
conhecimento específico sistematicamente precifica melhor.

**Regra prática:** só aposte em mercados onde você **consegue explicar
por que o preço está errado** antes de clicar.

---

### 2. Fading de sobre-reação a notícias (contra-tendência calibrada)

O mercado frequentemente **exagera** na reação a eventos noticiosos:
- Notícia negativa → preço cai mais do que deveria
- Notícia positiva → preço sobe mais do que deveria

**Como explorar:**
1. Quando um mercado cai muito rápido por uma notícia, calcule se o novo preço
   já precifica o downside completo ou está super-descontado.
2. Aposte na reversão **com tamanho pequeno** (5-8% do bankroll).
3. Meça: se o seu win rate nessas apostas for > 55%, você tem edge.

**Cuidado:** isso só funciona se a notícia for realmente "over-priced".
Tracked bets com tag "fade-news" para isolar a performance.

---

### 3. Calibração forçada com base rates

O mercado frequentemente ignora **base rates históricos**. Exemplos:

| Pergunta | Viés de mercado | Base rate real |
|----------|-----------------|----------------|
| "X vai conseguir FDA approval em 6 meses?" | Otimismo excessivo | Taxa histórica ~15-20% |
| "Campeonato vai ser cancelado por chuva?" | Ignora histórico local | Depende de dados locais |
| "Policial será indiciado?" | Recência/mídia | Taxa histórica baixa |

**Ação:**
1. Para cada mercado que te interessa, pesquise a **taxa base histórica**.
2. Se o mercado está > 10pp acima da base rate sem fator diferencial claro, venda.
3. Se está > 10pp abaixo, compre.

---

### 4. Velocidade em eventos com resolução clara e rápida

Alguns mercados têm resolução óbvia **antes** do preço se ajustar:
- Dados econômicos que saem ao meio-dia (CPI, NFP, etc.)
- Resultados de votações em tempo real
- Preços on-chain já visíveis na blockchain antes do mercado atualizar

**Como configurar:**
1. Use alertas (TradingView, CoinGecko, etc.) para eventos com timestamp fixo.
2. Tenha o mercado já aberto no browser antes do evento.
3. Execute em segundos após o dado sair — os primeiros 30-60 segundos têm
   o maior edge antes do mercado convergir.

---

### 5. Mercados perto da resolução com preço ainda incerto

Quando um mercado está a 24-72h de resolver e o outcome é quase certo
mas o preço ainda está em 0.85-0.92 (não em 0.98+), há alpha residual.

**Checklist:**
- [ ] O evento já aconteceu ou é irreversível?
- [ ] Só falta confirmação oficial?
- [ ] O preço ainda não é ≥ 0.97?
- [ ] Há liquidez suficiente para executar sem slippage?

Se tudo sim → compra com 5-10% do bankroll, risco máximo = tempo de espera.

---

## Fluxo diário com os commands

Use os slash commands do Claude Code para executar cada etapa:

| Etapa | Command | O que faz |
|-------|---------|-----------|
| 1. Encontrar oportunidades | `/scan` | Busca ~1000 mercados, filtra futebol europeu, entrega top 10 com score e Kelly sizing |
| 2. Registrar antes de apostar | `/log` | Salva sua estimativa de probabilidade, categoria e racional *antes* de executar |
| 3. Executar no Polymarket | *(manual)* | Coloca a posição no site |
| 4. Acompanhar e medir edge | `/tracker` | Sincroniza com a API, recalcula edge, win rate e gera REPORT.md |

> **Ordem:** `/scan` → decide → `/log` → aposta no site → `/tracker` quando resolver

---

## Sistema de tracking e validação de edge

Use o `tracker.py` deste repositório para medir seu edge automaticamente.

### Meta por estágio

| Apostas resolvidas | O que medir | Meta |
|--------------------|-------------|------|
| 0–20 | Não concluir nada — puro ruído | — |
| 20–50 | Identificar categorias com edge positivo | Edge > 0% |
| 50–100 | Confirmar edge estatisticamente | Edge ≥ +0.5% |
| 100+ | Escalar bankroll | Edge ≥ +1.0% |

### Regras de bankroll

- **Tamanho base por aposta:** 5% do bankroll
- **Alta convicção:** máximo 12%
- **Nunca mais de 20% em mercados correlacionados** (ex: duas eleições do mesmo país)
- **Stop loss:** se perder 30% do bankroll, pause e revise estratégia

### Tags para rastrear suas apostas

Quando registrar uma aposta, adicione uma tag de estratégia:
- `specialist` — edge por conhecimento de domínio
- `fade-news` — contra-tendência pós-notícia
- `base-rate` — mercado ignora taxa histórica
- `speed` — arbitragem de velocidade
- `near-resolution` — mercado quase resolvido

Depois de 50 apostas, compare o edge médio por tag para saber
**qual estratégia funciona para você**.

---

## O que NÃO fazer

- ❌ Apostar porque "parece óbvio" sem checklist
- ❌ Aumentar tamanho para recuperar perdas
- ❌ Apostar em mercados onde você não tem opinião diferente do mercado
- ❌ Ignorar spread/slippage em mercados com pouca liquidez
- ❌ Julgar performance por menos de 50 apostas resolvidas

---

## Checklist pré-aposta (30 segundos)

1. **Por que o mercado está errado?** (Se não consegue responder, não aposte)
2. **Qual é o base rate histórico para esse tipo de evento?**
3. **Qual categoria/estratégia é essa?**
4. **Qual é o meu tamanho (% do bankroll)?**
5. **Qual é o spread atual? Vale a pena pagar?**
