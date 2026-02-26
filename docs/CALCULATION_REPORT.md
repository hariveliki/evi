# Equal-Value-Index (EVI) Weights Calculator — Calculation Details Report

**Project:** `evi-weights` v1.0.0  
**Report Date:** 2026-02-26  
**Prepared for:** Further Studies

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Objective](#2-objective)
3. [Data Inputs](#3-data-inputs)
4. [Calculation Pipeline Overview](#4-calculation-pipeline-overview)
5. [Step-by-Step Calculation Details](#5-step-by-step-calculation-details)
   - 5.1 [Effective Date Computation](#51-effective-date-computation)
   - 5.2 [Baseline Computation](#52-baseline-computation)
   - 5.3 [Valuation Scoring](#53-valuation-scoring)
   - 5.4 [Score Winsorization](#54-score-winsorization)
   - 5.5 [Composite Score Combination](#55-composite-score-combination)
   - 5.6 [Adjustment Factor Computation](#56-adjustment-factor-computation)
   - 5.7 [Raw EVI Weight Computation](#57-raw-evi-weight-computation)
   - 5.8 [Normalization](#58-normalization)
   - 5.9 [Shrinkage Toward Market-Cap Weights](#59-shrinkage-toward-market-cap-weights)
   - 5.10 [Constraint Application](#510-constraint-application)
   - 5.11 [Turnover Cap](#511-turnover-cap)
6. [Configuration Parameters](#6-configuration-parameters)
7. [Regions Covered](#7-regions-covered)
8. [Data Generation Model (Sample Data)](#8-data-generation-model-sample-data)
9. [Worked Example](#9-worked-example)
10. [Key Design Decisions and Rationale](#10-key-design-decisions-and-rationale)
11. [Limitations and Assumptions](#11-limitations-and-assumptions)
12. [Source File Reference](#12-source-file-reference)

---

## 1. Executive Summary

The EVI Weights Calculator computes portfolio allocation weights for six global equity regions. Rather than weighting regions purely by market capitalization (which overweights expensive markets and underweights cheap ones), EVI adjusts market-cap weights using fundamental valuation signals — specifically trailing Price-to-Earnings (P/E) and Price-to-Book (P/B) ratios.

The core idea: **regions that are overvalued relative to their own history receive reduced weight; regions that are undervalued receive increased weight.**

The system implements a nine-step pipeline from raw valuation data to final constrained portfolio weights.

---

## 2. Objective

Produce a set of portfolio weights \( w_i \) for each region \( i \) such that:

- \( \sum_i w_i = 1 \)
- Regions trading at high valuations relative to their historical norms are underweighted
- Regions trading at low valuations relative to their historical norms are overweighted
- Weights respect practical portfolio constraints (floors, ceilings, turnover limits)

---

## 3. Data Inputs

### 3.1 Per-Region Required Data

For each region, the system requires:

| Field | Description |
|---|---|
| **Current P/E ratio** | Trailing 12-month price-to-earnings ratio as of the effective date |
| **Current P/B ratio** | Latest price-to-book ratio as of the effective date |
| **Historical P/E series** | Quarterly P/E observations over the lookback window |
| **Historical P/B series** | Quarterly P/B observations over the lookback window |
| **Market-cap weight** | The region's share of total global equity market capitalization |

### 3.2 Data Sources

The system supports three data sources:

1. **Sample data** (default): Deterministic synthetic data generated with seed=42, covering Q1 2014 through Q4 2025 (48 quarterly observations per region). The generator models trend, cyclicality, COVID-19 dip, post-COVID boom, and 2022 correction.
2. **JSON file**: Historical data loaded from a structured JSON file (see `data/sample_history.json`).
3. **Live data**: Real-time data fetched via `yfinance` using ETF tickers as proxies for regional indices. Falls back to sample data on failure.

### 3.3 Data Lag

A configurable `data_lag_days` (default: 5) is subtracted from the as-of date to produce the **effective date**, accounting for the delay between market close and data availability:

```
effective_date = as_of_date - data_lag_days
```

---

## 4. Calculation Pipeline Overview

The pipeline is executed per-region for Steps 1–5, then across all regions for Steps 6–9.

```
For each region:
  ┌─────────────────────────────────┐
  │ Step 1: Compute Baselines       │  Historical median/mean of P/E and P/B
  │ Step 2: Score Valuations        │  log(current / baseline) for each metric
  │ Step 3: Winsorize Scores        │  Clip extreme scores to [-2.5, +2.5]
  │ Step 4: Combine P/E & P/B      │  Weighted average: 0.6×PE + 0.4×PB
  │ Step 5: Compute Adjustment      │  exp(-k × composite_score)
  │ Step 6: Raw EVI Weight          │  mcap_weight × adjustment_factor
  └─────────────────────────────────┘

Across all regions:
  ┌─────────────────────────────────┐
  │ Step 7: Normalize               │  Weights sum to 1.0
  │ Step 8: Shrinkage to MCAP      │  Blend toward market-cap weights
  │ Step 9: Apply Constraints       │  Floor, ceiling, over/underweight limits
  │ Step 10: Turnover Cap           │  Limit period-over-period changes
  └─────────────────────────────────┘
```

---

## 5. Step-by-Step Calculation Details

### 5.1 Effective Date Computation

```
effective_date = as_of_date - timedelta(days=data_lag_days)
```

With default settings (`data_lag_days=5`), if as-of date is 2025-12-31, the effective date is 2025-12-26.

**Source:** `evi_weights/config.py`, `EVIConfig.effective_date` property.

---

### 5.2 Baseline Computation

For each valuation metric (P/E and P/B), a baseline is computed from historical data.

**Window selection:** Only observations where `cutoff ≤ date ≤ effective_date` are included, where:

```
cutoff = effective_date - lookback_years
```

Default `lookback_years = 10`.

**Minimum data requirement:** The system requires:
- At least `min_history_years` (default: 5) of history — verified by checking that the earliest data point predates `effective_date - min_history_years`
- At least `max(4, min_history_years × 4)` data points (i.e., at least 20 quarterly observations with default settings)
- All values must be positive (zero and negative values are excluded)

**Computation methods:**

| Method | Formula |
|---|---|
| `rolling_median` (default) | \( B_m = \text{median}(\{v_t : t \in [cutoff, effective]\}) \) |
| `rolling_mean` | \( B_m = \text{mean}(\{v_t : t \in [cutoff, effective]\}) \) |
| `fixed` | Uses the first value in the window |

If insufficient data exists, the baseline returns `None` and the metric is treated as missing.

**Source:** `evi_weights/calculator.py`, `compute_baseline()`.

---

### 5.3 Valuation Scoring

For each metric where both current value and baseline are available, a **valuation score** is computed.

**Scoring methods:**

| Method | Formula | Interpretation |
|---|---|---|
| `log_ratio` (default) | \( s = \ln\!\left(\dfrac{V_{\text{current}}}{B}\right) \) | Symmetric treatment of over/undervaluation on a log scale |
| `zscore` | \( s = \dfrac{V_{\text{current}} - B}{B} \) | Percentage deviation from baseline |
| `percentile` | \( s = \dfrac{V_{\text{current}} - B}{B} \) | Same as zscore (simplified) |

**Sign convention:**
- **Positive score** → current valuation **exceeds** baseline → region is **overvalued**
- **Negative score** → current valuation **below** baseline → region is **undervalued**
- **Zero** → current equals baseline → region is **fairly valued**

**Edge cases:** If either `current ≤ 0` or `baseline ≤ 0`, the score returns 0.0.

**Source:** `evi_weights/calculator.py`, `compute_score()`.

---

### 5.4 Score Winsorization

Extreme scores are clipped to prevent outliers from dominating the allocation.

```
s_clipped = max(lower_limit, min(upper_limit, s))
```

Default limits: `[-2.5, +2.5]`.

This bounds the maximum impact any single metric can have on the adjustment factor. With the default `exp_score` adjustment function and `k=0.8`, a score of ±2.5 produces an adjustment factor of \( e^{\mp 2.0} \approx 7.39 \) or \( 0.135 \), limiting the maximum tilt to roughly 7.4× the market-cap weight.

Winsorization can be disabled via configuration.

**Source:** `evi_weights/calculator.py`, `winsorize_score()`.

---

### 5.5 Composite Score Combination

The individual P/E and P/B scores are combined into a single composite valuation score per region using a weighted average.

**Formula (both metrics available):**

\[
S_{\text{composite}} = w_{PE} \cdot s_{PE} + w_{PB} \cdot s_{PB}
\]

Default weights: \( w_{PE} = 0.6 \), \( w_{PB} = 0.4 \).

**Missing metric handling** (controlled by `missing_metric_rule`):

| Rule | Behavior |
|---|---|
| `reweight` (default) | If one metric is missing, use the available metric's score at 100% weight. If both are missing, composite = 0.0 |
| `drop_region` | If any metric is missing, return NaN. The region is later excluded from the calculation entirely |
| `fallback_pb_only` | If P/E is missing, use P/B only (and vice versa). If both missing, composite = 0.0 |

**Source:** `evi_weights/calculator.py`, `combine_scores()`.

---

### 5.6 Adjustment Factor Computation

The composite score is transformed into a multiplicative adjustment factor that tilts the market-cap weight.

**Adjustment functions:**

| Function | Formula | Properties |
|---|---|---|
| `exp_score` (default) | \( f = e^{-k \cdot S_{\text{composite}}} \) | Always positive; \( f > 1 \) when undervalued (\( S < 0 \)); \( f < 1 \) when overvalued (\( S > 0 \)); \( f = 1 \) when fairly valued (\( S = 0 \)) |
| `inverse_ratio` | \( f = \dfrac{1}{\alpha + \beta \cdot e^{S_{\text{composite}}}} \) | Bounded; approaches \( 1/\alpha \) for strongly undervalued regions and approaches 0 for strongly overvalued regions |

**Default parameter:** \( k = 0.8 \) (strength parameter controlling sensitivity).

**Behavior of the default `exp_score` function:**

| Composite Score | Adjustment Factor | Effect |
|---|---|---|
| -1.0 (undervalued) | \( e^{0.8} \approx 2.23 \) | Weight roughly doubles |
| -0.5 | \( e^{0.4} \approx 1.49 \) | Weight increases ~49% |
| 0.0 (fair value) | 1.0 | No change |
| +0.5 (overvalued) | \( e^{-0.4} \approx 0.67 \) | Weight decreases ~33% |
| +1.0 | \( e^{-0.8} \approx 0.45 \) | Weight roughly halves |

If the composite score is NaN (from `drop_region` rule), the adjustment factor defaults to 1.0.

**Source:** `evi_weights/calculator.py`, `compute_adjustment_factor()`.

---

### 5.7 Raw EVI Weight Computation

The raw (unnormalized) EVI weight for each region is:

\[
w_i^{\text{raw}} = w_i^{\text{mcap}} \times f_i
\]

where \( w_i^{\text{mcap}} \) is the market-cap weight and \( f_i \) is the adjustment factor.

**Source:** `evi_weights/calculator.py`, line 378.

---

### 5.8 Normalization

Raw weights are normalized to sum to 1.0:

\[
w_i^{\text{norm}} = \frac{w_i^{\text{raw}}}{\sum_j w_j^{\text{raw}}}
\]

Regions with NaN composite scores (from the `drop_region` rule) are excluded before normalization.

**Source:** `evi_weights/calculator.py`, lines 393–395.

---

### 5.9 Shrinkage Toward Market-Cap Weights

To moderate the EVI tilt and improve robustness, the normalized EVI weights are blended back toward market-cap weights using a shrinkage parameter \( \lambda \):

\[
w_i^{\text{shrunk}} = (1 - \lambda) \cdot w_i^{\text{norm}} + \lambda \cdot w_i^{\text{mcap}}
\]

Default: \( \lambda = 0.20 \), meaning the final weight is 80% EVI signal and 20% market-cap anchor.

The shrunk weights are then re-normalized to sum to 1.0.

**Source:** `evi_weights/calculator.py`, lines 398–404.

---

### 5.10 Constraint Application

An iterative clip-and-redistribute algorithm enforces four constraints simultaneously:

| Constraint | Default Value | Description |
|---|---|---|
| **Weight floor** | 2% (0.02) | Minimum allocation to any region |
| **Weight ceiling** | 60% (0.60) | Maximum allocation to any region |
| **Max overweight** | +7.5 pp | Maximum increase vs. market-cap weight |
| **Max underweight** | -7.5 pp | Maximum decrease vs. market-cap weight |

**Algorithm:**

```
For up to 50 iterations:
  1. For each region i, compute effective bounds:
       lo_i = max(floor, mcap_i + max_underweight_pp / 100)
       hi_i = min(ceiling, mcap_i + max_overweight_pp / 100)
  2. Clip: w_i = clamp(w_i, lo_i, hi_i)
  3. Mark clipped regions as "frozen"
  4. Redistribute: scale unfrozen weights proportionally so that
       sum(frozen) + sum(unfrozen) = 1.0
  5. If no weight changed and total ≈ 1.0, stop
Final normalization if total ≠ 1.0
```

The absolute floor/ceiling constraints take priority over the relative over/underweight limits.

**Source:** `evi_weights/calculator.py`, `apply_constraints()`.

---

### 5.11 Turnover Cap

If previous period weights are provided, total portfolio turnover is limited:

\[
\text{turnover} = \sum_i |w_i^{\text{new}} - w_i^{\text{prev}}|
\]

If turnover exceeds the cap (default: 10 percentage points = 0.10):

```
scale = cap / total_turnover
w_i = w_i_prev + (w_i_new - w_i_prev) × scale
```

All changes are scaled proportionally, then weights are re-normalized.

**Source:** `evi_weights/calculator.py`, `apply_turnover_cap()`.

---

## 6. Configuration Parameters

All parameters are defined in `config.yaml` and loaded via `evi_weights/config.py`.

### 6.1 Top-Level Parameters

| Parameter | Default | Description |
|---|---|---|
| `as_of_date` | Today | Reference date for the calculation |
| `rebalance_frequency` | `quarterly` | How often weights are recalculated |
| `data_lag_days` | `5` | Days subtracted for data availability lag |

### 6.2 Valuation Inputs

| Parameter | Default | Description |
|---|---|---|
| `pe_type` | `trailing_12m` | Type of P/E ratio used |
| `pb_type` | `latest` | Type of P/B ratio used |
| `earnings_growth_type` | `null` | Reserved for future use |

### 6.3 Baseline Parameters

| Parameter | Default | Description |
|---|---|---|
| `baseline_method` | `rolling_median` | Statistical method for baseline |
| `lookback_years` | `10` | Historical window length |
| `min_history_years` | `5` | Minimum required history |

### 6.4 Scoring Parameters

| Parameter | Default | Description |
|---|---|---|
| `score_method` | `log_ratio` | How current vs. baseline is scored |
| `winsorize.enabled` | `true` | Whether to clip extreme scores |
| `winsorize.method` | `clip` | Winsorization method |
| `winsorize.limits` | `[-2.5, 2.5]` | Score clipping bounds |

### 6.5 Metric Combination

| Parameter | Default | Description |
|---|---|---|
| `metric_weights.pe` | `0.6` | Weight assigned to P/E score |
| `metric_weights.pb` | `0.4` | Weight assigned to P/B score |
| `missing_metric_rule` | `reweight` | How to handle missing metrics |

### 6.6 Adjustment Function

| Parameter | Default | Description |
|---|---|---|
| `function` | `exp_score` | Transformation function |
| `strength_k` | `0.8` | Sensitivity of adjustment to score |
| `alpha` | `0.5` | Parameter for `inverse_ratio` function |
| `beta` | `0.5` | Parameter for `inverse_ratio` function |

### 6.7 Constraint Parameters

| Parameter | Default | Description |
|---|---|---|
| `weight_floor` | `0.02` (2%) | Minimum weight per region |
| `weight_ceiling` | `0.60` (60%) | Maximum weight per region |
| `max_overweight_pp` | `7.5` pp | Max tilt above market-cap weight |
| `max_underweight_pp` | `-7.5` pp | Max tilt below market-cap weight |
| `shrinkage_to_mcap_lambda` | `0.20` | Blend toward market-cap (0=pure EVI, 1=pure MCAP) |
| `turnover_cap_pp` | `10.0` pp | Max total turnover per rebalance |

---

## 7. Regions Covered

| Region | Index Proxy | ETF Ticker |
|---|---|---|
| North America | S&P 500 | SPY |
| Europe | Stoxx Europe 600 | VGK |
| Emerging Markets | MSCI EM IMI | EEM |
| Small Caps | MSCI World Small Cap | VSS |
| Japan | MSCI Japan | EWJ |
| Pacific ex-Japan | MSCI Pacific ex-Japan | EPP |

---

## 8. Data Generation Model (Sample Data)

When using the built-in sample data generator, each region's valuation series is constructed from a parametric model:

\[
V_t = \text{base} + \text{trend} \times t + \text{cycle\_amp} \times \sin\!\left(\frac{2\pi t}{16}\right) + \text{shock}_t + \epsilon_t
\]

where:
- \( t \) is the quarter index (0 = Q1 2014)
- `base` is the starting level for the metric
- `trend` is a linear drift per quarter
- `cycle_amp` modulates a sinusoidal cycle with a period of 16 quarters (4 years)
- `shock_t` represents event-driven deviations:
  - **COVID dip** at quarter 24 (Q1 2020) with partial recovery in Q2 2020
  - **Post-COVID boom** ramping from Q3 2020 to peak at quarter 30 (Q3 2021)
  - **2022 correction** from peak to trough at quarter 33 (Q2 2022), recovering over 3 quarters
- \( \epsilon_t \sim \mathcal{N}(0, \text{base} \times \text{noise\_scale}) \) is Gaussian noise

Values are floored at 40% of the base level to prevent unrealistic readings.

Market-cap weights follow a simpler linear model with small Gaussian noise, floored at 1%, and normalized to sum to 1.0.

The random number generator uses a fixed seed (`seed=42`) for reproducibility.

**Source:** `evi_weights/data_provider.py`, `_generate_series()` and `generate_sample_data()`.

---

## 9. Worked Example

Using sample data for **North America** (as of 2025-12-31):

### Input Values
- Current P/E: 30.88
- Current P/B: 6.29
- Market-cap weight: ~75.2%

### Step 1 — Baseline (rolling median over 10 years)
From the sample history, the median P/E over the lookback window (2015-12-26 to 2025-12-26) yields a baseline around 25–27. The median P/B yields a baseline around 4.5–5.0.

### Step 2 — Score (log ratio)
```
PE score = ln(30.88 / baseline_PE)    → positive (overvalued)
PB score = ln(6.29 / baseline_PB)     → positive (overvalued)
```

### Step 3 — Winsorize
Both scores are within [-2.5, +2.5], so no clipping occurs.

### Step 4 — Composite
```
composite = 0.6 × PE_score + 0.4 × PB_score    → positive
```

### Step 5 — Adjustment Factor
```
factor = exp(-0.8 × composite)    → less than 1.0 (weight reduced)
```

### Step 6 — Raw Weight
```
raw_weight = 0.752 × factor    → less than 0.752
```

### Steps 7–10
After normalization, shrinkage (blending 20% toward MCAP), and constraint application, North America's final weight is reduced from its ~75.2% market-cap weight, reflecting its above-historical valuation levels.

Conversely, a region like **Emerging Markets** with a P/E of 11.57 (below its ~13.0 historical median) would receive a negative composite score, an adjustment factor > 1.0, and an increased final weight.

---

## 10. Key Design Decisions and Rationale

### 10.1 Log-Ratio Scoring
The log-ratio method treats overvaluation and undervaluation symmetrically on a multiplicative scale. A market trading at 2× its baseline produces the same magnitude score as one at 0.5× baseline, which is more appropriate for ratio-based financial metrics than linear deviations.

### 10.2 Exponential Adjustment Function
The `exp(-k × score)` function provides smooth, always-positive adjustment factors. The parameter `k` controls how aggressively the system tilts away from overvalued markets. Higher `k` → more aggressive value tilting.

### 10.3 Shrinkage Toward MCAP
Blending with market-cap weights serves as a regularizer. It reduces estimation error impact, keeps the portfolio investable for large allocators, and prevents extreme tilts when valuation signals are noisy. The default \( \lambda = 0.20 \) represents a moderately value-tilted strategy.

### 10.4 Rolling Median (vs. Mean) Baseline
The median is robust to outliers and structural breaks in the data. Extreme valuation episodes (e.g., the 2000 tech bubble) have less influence on the baseline compared to the mean.

### 10.5 P/E Overweighting (60/40)
P/E receives 60% weight because earnings-based valuation tends to be a stronger predictor of long-term returns than book-value-based metrics in the context of regional equity allocation. P/B provides diversification of the signal source.

### 10.6 Iterative Constraint Solver
The clip-and-redistribute algorithm handles interacting constraints (floor, ceiling, relative limits) that may conflict. Freezing clipped weights and redistributing among free weights ensures feasibility while maintaining proportional relationships among unconstrained regions.

---

## 11. Limitations and Assumptions

1. **Valuation metrics only**: The model uses only P/E and P/B ratios. It does not incorporate momentum, quality, growth, or macroeconomic factors.

2. **Mean reversion assumption**: The model assumes that regional valuations tend to revert to their historical medians. This may not hold during structural economic shifts.

3. **Regional granularity**: Six broad regions are used. Country-level or sector-level heterogeneity within regions is not captured.

4. **Quarterly frequency**: Baselines and rebalancing operate on a quarterly cadence. Short-term valuation swings within a quarter are not reflected.

5. **Sample data limitations**: The built-in data generator uses a simplified parametric model. Real data may exhibit fat tails, regime changes, and correlations not captured by the model.

6. **No transaction costs**: The turnover cap limits rebalancing magnitude but does not model explicit transaction costs, bid-ask spreads, or market impact.

7. **Equal liquidity assumption**: All regions are treated as equally liquid. In practice, Emerging Markets and Small Caps may face higher implementation costs.

8. **Earnings growth not used**: The `earnings_growth` field exists in the data model but is not currently used in any calculation.

---

## 12. Source File Reference

| File | Purpose |
|---|---|
| `main.py` | Entry point; invokes CLI |
| `config.yaml` | Default configuration parameters and region definitions |
| `evi_weights/__init__.py` | Package declaration and version |
| `evi_weights/config.py` | Configuration dataclasses and YAML loader |
| `evi_weights/models.py` | Data models: `ValuationSnapshot`, `RegionData`, `RegionScore`, `EVIResult` |
| `evi_weights/calculator.py` | Core calculation engine (all mathematical computations) |
| `evi_weights/data_provider.py` | Data loading, sample generation, JSON I/O, live fetch |
| `evi_weights/cli.py` | Command-line interface, output formatting |
| `data/sample_history.json` | Pre-generated sample data (48 quarters × 6 regions) |
| `tests/test_calculator.py` | Unit tests for individual calculation functions |
| `tests/test_config.py` | Unit tests for configuration loading |
| `tests/test_data_provider.py` | Unit tests for data providers |
| `tests/test_integration.py` | End-to-end pipeline tests and CLI smoke tests |

---

*End of report.*
