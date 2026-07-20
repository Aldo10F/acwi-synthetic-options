# Synthetic Options on the MSCI ACWI

Pricing and quoting options on the **iShares MSCI ACWI ETF** when no liquid listed options market is available: replicate the index with a basket of single-country ETFs, quote every option as a linear combination of options on the basket components, and validate the quotes with a realized delta-hedging backtest and a multivariate Monte Carlo of the hedging error.

The complete, executed analysis lives in [`acwi_synthetic_options.ipynb`](acwi_synthetic_options.ipynb).

**Authors:** Aldo Flores Mendoza & Alan Rogelio Urzúa Dettmer

## The problem

The MSCI All Country World Index (ACWI) covers large- and mid-cap equities across 47 developed and emerging markets, but there is no liquid options market on it. A desk asked to quote ACWI options therefore needs a replication strategy: build a synthetic ACWI from instruments that do have liquid options, price the requested options on the components, and hedge with the basket.

## Methodology

### 1. Data

Daily closes for the ACWI ETF and iShares country ETFs covering the ten largest country weights in the index, **2018-02-24 to 2024-02-24**:

| Country        | ETF  | Country     | ETF  |
|----------------|------|-------------|------|
| United States  | IVV (S&P 500) | France      | EWQ |
| Japan          | EWJ  | Germany     | EWG  |
| United Kingdom | EWU  | Switzerland | EWL  |
| China          | MCHI | India       | INDA |
| Canada         | EWC  | Taiwan      | EWT  |

[`fetch_data.py`](fetch_data.py) downloads the prices from Yahoo Finance and the risk-free rate from FRED and caches both under [`data/`](data/); the notebook reads only the cache, so it runs offline and every quote below reproduces exactly. Two price series are kept deliberately separate: **adjusted closes** for returns, regression and volatility (dividend drops are not risk), and **traded closes** for strikes and option pricing (strikes are quoted in traded-price terms, and an option holder does not receive dividends).

**Why the ETF and not the index itself?** The MSCI index (in [`data/IndexMSCI.csv`](data/IndexMSCI.csv)) is stamped at each regional market's close, while every ETF in the basket closes at the same time on NYSE. The notebook shows that this timing mismatch alone drops the replication R² from **0.993 (ETF target) to 0.946 (index target)**, a misalignment artifact, not a worse basket. The ETF also shares its closing time with the basket and is the underlying in whose terms the strikes are quoted.

### 2. Replicating regression

ACWI log returns are regressed (OLS) on the ten ETFs' log returns, **fitted only on data up to the valuation date** (2023-02-24, n = 1258). The weights define a hedge a desk puts on that day, so they must not be estimated on the option's own life; fitting through the end of the sample would tune the replication basket on the very path the backtest then grades it against.

Every ETF is individually significant (smallest |t| ≈ 5.3), so the basket is trimmed for parsimony rather than significance: the intercept (p = 0.31) and the three smallest legs (INDA, EWC and EWT, each under 4% of the basket) are dropped, and EWQ goes as a near-duplicate of EWG (ρ = 0.95; VIFs of ≈ 15 and ≈ 11 flag the redundancy). For a basket that is only ever traded as a whole, the collinearity-inflated individual standard errors behind a high VIF are harmless; the reason to drop the leg is that a near-duplicate is one more option to price and one more hedge to run for no additional information, and dropping either of the pair leaves R² at 0.993. The final 6-ETF model is re-estimated with heteroskedasticity-robust (HC3) errors:

```
r_ACWI = 0.6297·r_IVV + 0.0882·r_EWJ + 0.0869·r_EWU
       + 0.0685·r_MCHI + 0.0719·r_EWG + 0.0532·r_EWL + ε        (R² = 0.993)
```

Model assumptions are checked explicitly: post-screen VIFs all below 10 (max ≈ 6), Shapiro–Wilk on residuals (normality rejected, as usual for daily returns; OLS point estimates remain consistent), one-sample t-test (residual mean 0 not rejected, p ≈ 0.82), Durbin–Watson ≈ 2.54, plus residuals-vs-fitted and QQ plots and the full correlation matrix of returns. A 2-year rolling-window re-estimation over the full sample shows the weights drift gradually (IVV from ~0.57 in 2020 to ~0.66 at the valuation date and ~0.67 by 2024) with no regime breaks: enough stability to justify static weights over the option horizon, and enough drift to justify stopping the fit at the valuation date.

The normalized coefficients are the **synthetic ACWI** weights. A \$1,000,000 investment tracked in both the ACWI and the synthetic basket ends the in-sample window \$11.6k ahead of the ACWI on \$1.30M and drifts a further \$17.4k over the out-of-sample year, at **1.17% annualized tracking error out of sample** — a genuine held-out test of the replication, over exactly the window the options live in.

### 3. Market parameters as of the valuation date (2023-02-24)

Everything is estimated with information available on the valuation date only, the regression weights included:

- **Risk-free rate:** all these ETFs are USD-denominated assets trading on NYSE, so a single USD rate discounts everything. The 1-year Treasury yield (FRED series `DGS1`, 5.05% on the valuation date), maturity-matched to the 9- and 12-month options.

- **Dividend yields:** per-ETF average over the preceding sample, estimated as the log gap between total return (adjusted prices) and price return. Averaging smooths non-recurring special distributions (in the 10-ETF universe, EWT's Dec-2022 capital-gains distribution alone would push a trailing 12-month yield to ~17%).

- **Volatility:** two estimates per ETF and for the synthetic index, both computable on the valuation date: historical (20.38% for the synthetic) and EWMA (RiskMetrics, λ = 0.94, 14.59%), which weights the recent past more heavily. Every option is quoted under both.

### 4. Strike mapping and pricing

Quoted strikes are in ACWI-ETF terms (e.g. \$85). Each component option keeps the same moneyness as the ACWI option: `K_i = S_i · K / S_ACWI`, using traded prices.

The regression coefficients are **log-return exposures**, so the tradeable replica holds a dollar fraction `w_i` of each leg: `n_i = w_i · S_ACWI / S_i` shares of leg i, a basket worth exactly S_ACWI on the valuation date. Holding `w_i` shares instead would weight the basket by price level — IVV trades near \$400 against \$25–60 for the rest, making such a basket 94% IVV by value: an S&P 500 tracker, not an ACWI one, that ends the 12-month option horizon \$5.19 above the actual ACWI where the dollar-weighted basket ends \$0.73 below it (tracking error 3.04% vs 1.17% annualized; the notebook prints both). Quotes aggregate with the same units: a proportional payoff (call, spread) is worth Σ nᵢCᵢ, the digital's fixed \$1 payoff aggregates with the weights themselves, so every price below is in ACWI-ETF terms.

Three options are priced with Black–Scholes with continuous dividend yield as of 2023-02-24 and marked to market daily over their whole life, per component and aggregated into the synthetic quote:

| Option | Maturity | Strike(s) | Price | Delta |
|---|---|---|---|---|
| European call | 9 months | \$85 | `S·e^(−qT)·N(d1) − K·e^(−rT)·N(d2)` | `e^(−qT)·N(d1)` |
| Digital call (cash-or-nothing, pays \$1) | 9 months | \$87 | `e^(−rT)·N(d2)` | `e^(−rT)·φ(d2)/(S·σ·√T)` |
| Call spread | 12 months | \$78 / \$100 | `C(K₁) − C(K₂)` | `Δ(K₁) − Δ(K₂)` |

**Two deltas, and they are not the same number.** The *basket delta* (Σ wᵢΔᵢ) is the delta of what is actually sold. The *on-basket delta* treats the synthetic index as a single asset at its own vol and is what the backtest and Monte Carlo actually trade — 64.90% vs 65.45% on the call, 40.96% vs 43.73% on the spread. Both are reported in every pricing table, because the gap between them is the same basket-vs-option-on-basket distinction that produces the correlation premium below.

Every emitted quote is guarded by **no-arbitrage assertions**, checked per component and aggregated on every mark-to-market day: `max(S·e^−qT − K·e^−rT, 0) ≤ C ≤ S·e^−qT`, `0 ≤ digital ≤ e^−rT`, `0 ≤ spread ≤ (K₂−K₁)·e^−rT`, plus put–call parity on the pricing functions themselves. They cost nothing while they pass; a scaling or weighting mistake blows through the upper bounds immediately, so the notebook refuses to emit an out-of-bounds quote rather than relying on the numbers happening to look reasonable.

### 5. Basket of options vs option on the basket

A linear combination of options is not an option on the linear combination. For convex payoffs (the vanilla call), Jensen's inequality plus imperfect correlations make the basket of calls worth more than the call on the synthetic index; the basket super-replicates it, and the gap is the correlation premium embedded in the quote (\$0.49 on the 9-month call: \$9.258 vs \$8.765). For non-convex payoffs (the digital, the capped spread) the inequality does not apply and the sign flips, as the notebook's comparison table shows. The implied volatility backed out of the basket quote by root-finding (Brent's method) is **22.17%** vs the basket's own 20.38% historical vol.

### 6. Skew sensitivity

Flat-vol Black–Scholes is weakest exactly where the digital and the spread live: next to their strikes. On a real surface a cash-or-nothing digital is the tight-call-spread limit `−∂C/∂K` taken *along the skew*, which adds `−Vega·∂σ/∂K` to the flat-vol price — with the negative skew typical of equity indices, a positive correction. There is no listed ACWI surface to calibrate to (that absence is the premise of the exercise), so the headline quotes stay flat-vol and the exposure is quantified instead: every leg is repriced under a linear skew in log-moneyness with slopes swept from 0 to −3 vol points per 10% of moneyness (the equity-index range), the digital repriced as the ±1% call spread a desk would actually trade. At the steep end the vanilla call moves +3.3% (the \$9.26 headline is robust), while the digital gains up to +18.8% and the spread up to +20.7%: under a realistic skew both near-strike products are *under-quoted* by flat vol.

### 7. Validation: realized backtest and multivariate Monte Carlo

Each option is sold at its basket quote and delta-hedged daily with the synthetic underlying until expiry; cash accrues at the USD rate, the stock position earns its dividend yield, and the terminal hedging P&L is reported against the premium. Because one realized path proves little on its own, and because a single-asset simulation cannot produce correlation P&L by construction, the hedging experiment is repeated over **5,000 jointly simulated paths of the six legs** (correlated GBMs, correlation matrix estimated on the same pre-valuation window as the vols), for all three products, under two scenarios: realized vols equal to the quoted vols, and realized vols equal to the EWMA estimates.

**What the Monte Carlo does and does not prove.** The mean hedging P&L at the quoted vols matches the correlation premium of the pricing section for all three products (+\$0.52 vs +\$0.49 on the call, −\$0.007 vs −\$0.008 on the digital, −\$0.134 vs −\$0.132 on the spread). That is a strong consistency check, but calling it two *independent* computations of the premium would overstate it: under the risk-neutral measure a self-financing delta strategy has zero expected P&L whatever delta it uses, so the simulated mean is exactly `quote − E_Q[payoff]`, while the pricing table is `quote − P_BS(v_syn)` — the same quantity with the expectation replaced by a Black–Scholes value. It also does not establish that the premium exists: for a convex payoff that is Jensen's inequality, a theorem.

The residual three cents on the call is not approximation noise, and the notebook reconciles it explicitly. `v_syn` is `std(Σ wᵢrᵢ) = √(w′Σw)`, the volatility of a **constant-weight** basket, one rebalanced back to `w` every day. What is quoted, hedged and delivered is a **fixed-share** basket: the weights drift as the legs move, and over the option's life it realizes about 10bp less vol (20.28% against 20.38%). Repricing the option on the basket at the vol the simulated basket actually realizes gives a premium of \$0.5201 against the Monte Carlo's measured \$0.5208 — agreement to a tenth of a cent, with the genuine lognormal-approximation and discrete-rebalancing error being what is left.

The part that is not mechanical is the **hedge-vol sweep**. The mean P&L is flat at ≈ +\$0.52 across hedging vols from 10.4% to 27.2%, so the premium is not an artifact of hedging at one particular vol. What the hedging vol controls is dispersion: the standard deviation is minimized near the basket's own 20.4% (\$0.37), widens to \$0.42 at the quote's 22.2% implied, and blows out to \$1.55 at 10.4%. Hedging at the vol the basket actually realizes does not *earn* the premium — it earns it **reliably**. The premium is payment for carrying the aggregation risk between a basket of options and an option on the basket.

### Results at a glance (synthetic ACWI quote, 2023-02-24; single realized path vs Monte Carlo band)

| Option | Price (hist. vol) | Price (EWMA vol) | Realized hedge P&L (% premium) | MC mean [5th–95th], realized σ = EWMA |
|---|---|---|---|---|
| Call 9m, K = \$85 | \$9.26 | \$7.82 | +23.6% | +20.6% [+11.2%, +31.5%] |
| Digital call 9m, K = \$87 | \$0.518 | \$0.550 | −41.3% | −7.8% [−51.5%, +37.2%] |
| Call spread 12m, K = \$78/\$100 | \$10.43 | \$10.87 | −34.3% | −6.0% [−24.6%, +13.2%] |

The call's realized +23.6% sits near the middle of its Monte Carlo band: 2023 delivered volatility well below the 20.4% quoted, and the EWMA scenario prices exactly that regime. The digital's −41.3% is inside its wide band — concentrated gamma, now with a distribution around it instead of a single anecdote.

The spread's −34.3% falls *below* its 5th percentile, and two things contribute. 2023–24 was a nearly one-way rally through the short strike, the kind of trending path a GBM with independent increments underweights; and the skew sweep shows the flat-vol quote understates the spread by up to 20.7%, so a desk quoting on a real surface would have collected a materially larger premium against the same hedging losses. The band carries the model's own assumptions, not just its parameters, and a result outside it is a statement about the model as much as about the path. Per-component prices, deltas, daily mark-to-market series and all charts are in the notebook.

## Repository structure

```
.
├── acwi_synthetic_options.ipynb   # the complete, executed analysis
├── fetch_data.py                  # downloads and caches the market data
├── data/
│   ├── prices.csv                 # cached adjusted + traded closes (written by fetch_data.py)
│   ├── params.json                # window, tickers, risk-free rate (written by fetch_data.py)
│   └── IndexMSCI.csv              # MSCI ACWI index levels (for the ETF-vs-index comparison)
├── requirements.txt
├── README.md
└── LICENSE
```

## Reproducing

Requires Python ≥ 3.10. Only `fetch_data.py` needs an internet connection; the notebook itself runs entirely off the cache.

```bash
git clone <this-repo>
cd <this-repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python fetch_data.py                 # refresh the cache (already committed, so optional)
jupyter lab acwi_synthetic_options.ipynb
```

Run all cells (~10 seconds, since nothing is downloaded).

### Analysing a different window

`fetch_data.py` takes the sample window, the valuation date and the ticker universe as arguments, and writes both the prices and the parameters the notebook reads:

```bash
python fetch_data.py --start 2015-01-01 --end 2021-01-01 --valuation-date 2020-01-02
```

Re-run all cells and every number follows: the regression refits on the new pre-valuation window, the option horizons are derived from the valuation date rather than hardcoded, and the no-arbitrage guards re-run against the new quotes. Two things stay manual by design: the strikes (\$85 / \$87 / \$78 / \$100) are the terms of this exercise and are moneyness-sensible only near the ACWI's 2023 price, and the basket trim drops INDA/EWC/EWT/EWQ by name, so a different ticker universe means revisiting that screen.

### Reproducibility notes

- The notebook is deterministic: it reads a committed price cache, and the Monte Carlo is seeded (`seed=42`), so repeated runs return identical quotes and identical P&L distributions. Re-running `fetch_data.py` is the only thing that can move a number.
- Option pricing runs on traded (unadjusted) closes, which never get restated. Adjusted closes, used for returns, volatilities and dividend-yield estimation, are rescaled by Yahoo whenever a new dividend is paid, so refreshing the cache can move regression coefficients and vols at the fourth decimal.
- Yahoo occasionally serves adjusted closes with the dividend adjustment missing, which silently corrupts every return-based number. `fetch_data.py` asserts that each fund's total return beats its price return and fails loudly instead of writing a corrupt cache; if it fires, just re-run it.
- The no-arbitrage guards and put–call parity assertions run on every execution, so a corrupted cache or a reintroduced scaling bug fails the run loudly instead of producing plausible-looking bad quotes.
- The only market inputs are Yahoo Finance prices and the FRED `DGS1` rate; nothing is hardcoded from unverifiable sources.

## Limitations

Flat-vol Black–Scholes remains the pricing engine: the skew sweep quantifies the near-strike products' exposure but the headline quotes carry no smile or term structure. The Monte Carlo assumes constant Gaussian correlation (no stochastic correlation, no fat tails or trend persistence — the spread backtest shows what that omits), and the hedging simulations carry no transaction costs. The replication weights are static over the option horizon, which the rolling-window diagnostic supports but does not make free. These are conscious scope choices; each would refine the quotes without changing the architecture of the approach.
