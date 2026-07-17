# Synthetic Options on the MSCI ACWI

Pricing and quoting options on the **iShares MSCI ACWI ETF** when no liquid listed options market is available: replicate the index with a basket of single-country ETFs, quote every option as a linear combination of options on the basket components, and validate the quotes with a realized delta-hedging backtest and a multivariate Monte Carlo of the hedging error in which the correlation premium embedded in the quotes shows up as realized P&L.

The complete, executed analysis lives in [`acwi_synthetic_options.ipynb`](acwi_synthetic_options.ipynb).

**Authors:** Aldo Flores Mendoza & Alan Rogelio Urzúa Dettmer

## The problem

The MSCI All Country World Index (ACWI) covers large- and mid-cap equities across 47 developed and emerging markets, but there is no liquid options market on it. A desk asked to quote ACWI options therefore needs a replication strategy: build a synthetic ACWI from instruments that do have liquid options, price the requested options on the components, and hedge with the basket.

## Methodology

### 1. Data

Daily closes from Yahoo Finance, **2018-02-24 to 2024-02-24**, for the ACWI ETF and iShares country ETFs covering the ten largest country weights in the index:

| Country        | ETF  | Country     | ETF  |
|----------------|------|-------------|------|
| United States  | IVV (S&P 500) | France      | EWQ |
| Japan          | EWJ  | Germany     | EWG  |
| United Kingdom | EWU  | Switzerland | EWL  |
| China          | MCHI | India       | INDA |
| Canada         | EWC  | Taiwan      | EWT  |

Two price series are kept deliberately separate: **adjusted closes** for returns, regression and volatility (dividend drops are not risk), and **traded closes** for strikes and option pricing (strikes are quoted in traded-price terms, and an option holder does not receive dividends).

**Why the ETF and not the index itself?** The MSCI index (in [`data/IndexMSCI.csv`](data/IndexMSCI.csv)) is stamped at each regional market's close, while every ETF in the basket closes at the same time on NYSE. The notebook shows that this timing mismatch alone drops the replication R² from **0.993 (ETF target) to 0.945 (index target)**, a misalignment artifact, not a worse basket. The ETF also shares its closing time with the basket and is the underlying in whose terms the strikes are quoted.

### 2. Replicating regression

ACWI log returns are regressed (OLS) on the ten ETFs' log returns. Every ETF is individually significant (only the intercept is not, p ≈ 0.40), so the basket is trimmed for parsimony rather than significance: the intercept and the three smallest legs (INDA, EWC and EWT, each under 4% of the basket) are dropped, and EWQ goes as a near-duplicate of EWG (ρ = 0.95; VIFs of ≈ 14 and ≈ 11 flag the redundancy). For a basket that is only ever traded as a whole, the collinearity-inflated individual standard errors behind a high VIF are harmless, the reason to drop the leg is that a near-duplicate is one more option to price and one more hedge to run for no additional information, and dropping either of the pair leaves R² at 0.993. The final 6-ETF model is re-estimated with heteroskedasticity-robust (HC3) errors:

```
r_ACWI = 0.6351·r_IVV + 0.0867·r_EWJ + 0.0861·r_EWU
       + 0.0659·r_MCHI + 0.0739·r_EWG + 0.0505·r_EWL + ε        (R² = 0.993)
```

Model assumptions are checked explicitly: post-screen VIFs all below 10 (max ≈ 6; the surviving European legs still co-move, which widens their individual confidence intervals but not the joint fit of a basket that is only ever traded as a whole), Shapiro–Wilk on residuals (normality rejected, as usual for daily returns, OLS point estimates remain consistent), one-sample t-test (residual mean 0 not rejected, p ≈ 0.99), Durbin–Watson ≈ 2.5, plus residuals-vs-fitted and QQ plots and the full correlation matrix of returns. A 2-year rolling-window re-estimation shows the weights drift gradually (IVV from ~0.56 to ~0.67 as the US weight in the index grew) with no regime breaks, supporting static weights over the valuation horizon.

The normalized coefficients are the **synthetic ACWI** weights. As a sanity check, a \$1,000,000 investment on 2018-02-24 is tracked through 2024-02-24 in both the ACWI and the synthetic basket; the two equity curves move together throughout and end within \$300 of each other (≈ \$1.603M both).

### 3. Market parameters as of the valuation date (2023-02-24)

Everything is estimated with information available on the valuation date only:

- **Risk-free rate:** all these ETFs are USD-denominated assets trading on NYSE, so a single USD rate discounts everything. The 1-year Treasury yield (FRED series `DGS1`, 5.05% on the valuation date), maturity-matched to the 9- and 12-month options and fetched programmatically rather than hardcoded.

- **Dividend yields:** per-ETF 5-year average, estimated as the log gap between total return (adjusted prices) and price return. Averaging smooths non-recurring special distributions (in the 10-ETF universe, EWT's Dec-2022 capital-gains distribution alone would push a trailing 12-month yield to ~17%).

- **Volatility:** two estimates per ETF and for the synthetic index, both computable on the valuation date; 5-year historical, and EWMA (RiskMetrics, λ = 0.94), which weights the recent past more heavily. Every option is quoted under both. 

### 4. Strike mapping and pricing

Quoted strikes are in ACWI-ETF terms (e.g. \$85). Each component option keeps the same moneyness as the ACWI option: `K_i = S_i · K / S_ACWI`, using traded prices.

The regression coefficients are **log-return exposures**, so the tradeable replica holds a dollar fraction `w_i` of each leg: `n_i = w_i · S_ACWI / S_i` shares of leg i, a basket worth exactly S_ACWI on the valuation date. Holding `w_i` shares instead would weight the basket by price level, IVV trades near \$400 against \$25–60 for the rest, making such a basket 94% IVV by value: an S&P 500 tracker, not an ACWI one, that ends the 12-month option horizon \$5.23 above the actual ACWI where the dollar-weighted basket ends \$0.59 below it (tracking error 3.1% vs 1.2% annualized; the notebook prints both). Quotes aggregate with the same units, a proportional payoff (call, spread) is worth Σ nᵢCᵢ, the digital's fixed \$1 payoff aggregates with the weights themselves, so every price below is in ACWI-ETF terms.

Three options are priced with Black–Scholes with continuous dividend yield as of 2023-02-24 and marked to market daily over their whole life, per component and aggregated into the synthetic quote with the replication units:

| Option | Maturity | Strike(s) | Price | Delta |
|---|---|---|---|---|
| European call | 9 months | \$85 | `S·e^(−qT)·N(d1) − K·e^(−rT)·N(d2)` | `e^(−qT)·N(d1)` |
| Digital call (cash-or-nothing, pays \$1) | 9 months | \$87 | `e^(−rT)·N(d2)` | `e^(−rT)·φ(d2)/(S·σ·√T)` |
| Call spread | 12 months | \$78 / \$100 | `C(K₁) − C(K₂)` | `Δ(K₁) − Δ(K₂)` |

Every emitted quote is guarded by **no-arbitrage assertions**, checked per component and aggregated on every mark-to-market day: `max(S·e^−qT − K·e^−rT, 0) ≤ C ≤ S·e^−qT`, `0 ≤ digital ≤ e^−rT`, `0 ≤ spread ≤ (K₂−K₁)·e^−rT`, plus put–call parity on the pricing functions themselves. They cost nothing while they pass; a scaling or weighting mistake blows through the upper bounds immediately, so the notebook refuses to emit an out-of-bounds quote rather than relying on the numbers happening to look reasonable.

### 5. Basket of options vs option on the basket

A linear combination of options is not an option on the linear combination. For convex payoffs (the vanilla call), Jensen's inequality plus imperfect correlations make the basket of calls worth more than the call on the synthetic index; the basket super-replicates it, and the gap is the correlation premium embedded in the quote (\$0.48 on the 9-month call). For non-convex payoffs (the digital, the capped spread) the inequality does not apply and the sign flips, as the notebook's comparison table shows. The implied volatility backed out of the basket quote by root-finding (Brent's method) is **22.2%** vs the basket's own 20.4% historical vol.

### 6. Skew sensitivity

Flat-vol Black–Scholes is weakest exactly where the digital and the spread live: next to their strikes. On a real surface a cash-or-nothing digital is the tight-call-spread limit `−∂C/∂K` taken *along the skew*, which adds `−Vega·∂σ/∂K` to the flat-vol price, with the negative skew typical of equity indices, a positive correction. There is no listed ACWI surface to calibrate to (that absence is the premise of the exercise), so the headline quotes stay flat-vol and the exposure is quantified instead: every leg is repriced under a linear skew in log-moneyness with slopes swept from 0 to −3 vol points per 10% of moneyness (the equity-index range), the digital repriced as the ±1% call spread a desk would actually trade. At the steep end the vanilla call moves +3.3%, the \$9.26 headline is robust, while the digital gains up to +18.8% and the spread up to +20.7%: under a realistic skew both near-strike products are *under-quoted* by flat vol, and part of their negative hedging P&L below is a flat-vol artifact rather than pure concentrated gamma.

### 7. Validation: realized backtest and multivariate Monte Carlo

Each option is sold at its basket quote and delta-hedged daily with the synthetic underlying until expiry, cash accrues at the USD rate, the stock position earns its dividend yield, and the terminal hedging P&L is reported against the premium. Because one realized path proves little on its own, and because a single-asset simulation cannot produce correlation P&L by construction, the hedging experiment is repeated over **5,000 jointly simulated paths of the six legs** (correlated GBMs, correlation matrix estimated on the same window as the vols), for all three products, under two scenarios: realized vols equal to the quoted vols, where the mean P&L isolates what the aggregation itself earns or costs, and realized vols equal to the EWMA estimates, the embedded margin if the recent lower-vol regime persists.

The first scenario closes the loop on the pricing thesis: the mean hedging P&L reproduces the correlation premium of the pricing section for all three products, **+\$0.51 realized vs +\$0.48 quoted** on the call, and matching to the cent on the digital (−\$0.01) and the spread (−\$0.13). The premium charged for imperfect correlation is not a pricing footnote; it is collected path by path by the seller who hedges the basket, with the sign flipping for the non-convex payoffs exactly as the comparison table predicts.

### Results at a glance (synthetic ACWI quote, 2023-02-24; single realized path vs Monte Carlo band)

| Option | Price (hist. vol) | Price (EWMA vol) | Realized hedge P&L (% premium) | MC mean [5th–95th], realized σ = EWMA |
|---|---|---|---|---|
| Call 9m, K = \$85 | \$9.26 | \$7.81 | +23.5% | +20.5% [+11.1%, +31.5%] |
| Digital call 9m, K = \$87 | \$0.52 | \$0.55 | −41.3% | −7.9% [−51.6%, +37.1%] |
| Call spread 12m, K = \$78/\$100 | \$10.43 | \$10.87 | −34.2% | −6.0% [−24.7%, +13.3%] |

The call's realized +23.5% sits near the middle of its Monte Carlo band: 2023 delivered volatility well below the 20.4% quoted, and the EWMA scenario prices exactly that regime. The digital's −41.3% is inside its wide band, concentrated gamma near the strike, now with a distribution around it instead of a single anecdote, and partly a flat-vol artifact (the skew sweep shows a desk would quote it 6–19% higher). The spread's −34.2% falls *below* its 5th percentile: 2023–24 was a nearly one-way rally through the short strike, the kind of trending path a GBM with independent increments underweights, the bands carry the model's own assumptions, not just its parameters. Per-component prices, deltas, daily mark-to-market series and all charts are in the notebook.

## Repository structure

```
.
├── acwi_synthetic_options.ipynb   # the complete, executed analysis
├── data/
│   └── IndexMSCI.csv              # MSCI ACWI index levels (for the ETF-vs-index comparison)
├── requirements.txt
├── README.md
└── LICENSE
```

## Reproducing

Requires Python ≥ 3.10 and an internet connection (prices come from Yahoo Finance and the risk-free rate from FRED at run time).

```bash
git clone <this-repo>
cd <this-repo>
python3 -m venv .venv
source .venv/bin/activate 
pip install -r requirements.txt 
jupyter lab acwi_synthetic_options.ipynb
```

Run all cells (~2 minutes).

### Reproducibility notes

- Option pricing runs on traded (unadjusted) closes, which never get restated, so the quotes are stable across runs. Adjusted closes used only for returns, volatilities and dividend-yield estimation are rescaled by Yahoo whenever a new dividend is paid, so regression coefficients and vols can move at the fourth decimal.
- Yahoo occasionally serves adjusted closes with the dividend adjustment missing, which silently corrupts every return-based number. The download cell asserts that each fund's total return beats its price return and fails loudly instead; if it fires, just re-run the cell.
- The Monte Carlo is seeded, so its numbers are exactly reproducible.
- The no-arbitrage guards and put–call parity assertions run on every execution, so a corrupted download or a reintroduced scaling bug fails the run loudly instead of producing plausible-looking bad quotes.
- The only market inputs are Yahoo Finance prices and the FRED `DGS1` rate, all fetched at run time as of the valuation date; nothing is hardcoded from unverifiable sources.

## Limitations

Flat-vol Black–Scholes remains the pricing engine: the skew sweep quantifies the near-strike products' exposure but the headline quotes carry no smile or term structure, the Monte Carlo assumes constant Gaussian correlation (no stochastic correlation, no fat tails or trend persistence, the spread backtest shows what that omits), and the hedging simulations carry no transaction costs. These are conscious scope choices; each would refine the quotes without changing the architecture of the approach.
