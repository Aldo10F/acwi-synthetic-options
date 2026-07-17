# Synthetic Options on the MSCI ACWI

Pricing and quoting options on the **iShares MSCI ACWI ETF** when no liquid listed options market is available: replicate the index with a basket of single-country ETFs, quote every option as a linear combination of options on the basket components, and validate the quotes with a realized delta-hedging backtest and a Monte Carlo of the hedging error.

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

ACWI log returns are regressed (OLS) on the ten ETFs' log returns. Every ETF is individually significant (only the intercept is not, p ≈ 0.40), so the basket is trimmed for parsimony rather than significance: the intercept and the three smallest legs (INDA, EWC and EWT, each under 4% of the basket) are dropped. A VIF screen on the survivors then flags EWQ (≈ 14) and EWG (≈ 11) as near-duplicates (ρ = 0.95); standard backward elimination removes the largest VIF being EWQ after which every VIF sits below 10 (max ≈ 6) and the final 6-ETF model is re-estimated with heteroskedasticity-robust (HC3) errors:

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

Three options are priced with Black–Scholes with continuous dividend yield as of 2023-02-24 and marked to market daily over their whole life, per component and aggregated into the synthetic quote with the regression weights:

| Option | Maturity | Strike(s) | Price | Delta |
|---|---|---|---|---|
| European call | 9 months | \$85 | `S·e^(−qT)·N(d1) − K·e^(−rT)·N(d2)` | `e^(−qT)·N(d1)` |
| Digital call (cash-or-nothing, pays \$1) | 9 months | \$87 | `e^(−rT)·N(d2)` | `e^(−rT)·φ(d2)/(S·σ·√T)` |
| Call spread | 12 months | \$78 / \$100 | `C(K₁) − C(K₂)` | `Δ(K₁) − Δ(K₂)` |

### 5. Basket of options vs option on the basket

A linear combination of options is not an option on the linear combination. For convex payoffs (the vanilla call), Jensen's inequality plus imperfect correlations make the basket of calls worth more than the call on the synthetic index; the basket super-replicates it, and the gap is the correlation premium embedded in the quote (\$1.25 on the 9-month call). For non-convex payoffs (the digital, the capped spread) the inequality does not apply and the sign can flip, as the notebook's comparison table shows. The implied volatility backed out of the basket quote by root-finding (Brent's method) is **21.9%** vs the basket's own 20.4% historical vol.

### 6. Validation: realized backtest and Monte Carlo

Each option is sold at its basket quote and delta-hedged daily with the synthetic underlying until expiry, cash accrues at the USD rate, the stock position earns its dividend yield, and the terminal hedging P&L is reported against the premium. Because one realized path proves little on its own, the hedging experiment is then repeated over **5,000 simulated GBM paths** of the synthetic index under two scenarios: realized vol equal to the quoted vol (validating the hedging machinery: mean P&L ≈ 0, dispersion = discrete-rebalancing error) and realized vol equal to the EWMA estimate (the quote's embedded margin if recent volatility persists).

### Results at a glance (synthetic ACWI quote, 2023-02-24)

| Option | Price (hist. vol) | Price (EWMA vol) | Realized hedge P&L (% premium) |
|---|---|---|---|
| Call 9m, K = \$85 | \$28.18 | \$23.84 | +18.6% |
| Digital call 9m, K = \$87 | \$0.52 | \$0.55 | −35.9% |
| Call spread 12m, K = \$78/\$100 | \$31.97 | \$33.40 | −28.7% |

Monte Carlo, short call 9m at the historical-vol quote: mean P&L **0.0% ± 4.2%** of premium when realized vol equals the quoted vol, and **+18.2%** (5th percentile +7.4%) when realized vol equals the EWMA, consistent with the +18.6% actually realized over 2023, when volatility came in well below the 20% quoted. The digital's loss is the expected behavior of concentrated gamma near the strike, the reason desks quote digitals with an extra margin or replicate them with a tight call spread. Per-component prices, deltas, daily mark-to-market series and all charts are in the notebook.

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

Run all cells (~1 minute).

### Reproducibility notes

- Option pricing runs on traded (unadjusted) closes, which never get restated, so the quotes are stable across runs. Adjusted closes used only for returns, volatilities and dividend-yield estimation are rescaled by Yahoo whenever a new dividend is paid, so regression coefficients and vols can move at the fourth decimal.
- Yahoo occasionally serves adjusted closes with the dividend adjustment missing, which silently corrupts every return-based number. The download cell asserts that each fund's total return beats its price return and fails loudly instead; if it fires, just re-run the cell.
- The Monte Carlo is seeded, so its numbers are exactly reproducible.
- The only market inputs are Yahoo Finance prices and the FRED `DGS1` rate, all fetched at run time as of the valuation date; nothing is hardcoded from unverifiable sources.

## Limitations

Flat-vol Black–Scholes: no volatility smile/skew or term structure, no correlation model beyond the historical vol of the basket, and no transaction costs in the hedging simulations. These are conscious scope choices, each would refine the quotes without changing the architecture of the approach.
