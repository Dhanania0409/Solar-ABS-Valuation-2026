# Rooftop Solar Loan Trust 2026 — Solar ABS Valuation Model

An end-to-end Python model that builds, values, and stress-tests an asset-backed security (ABS) collateralised by a synthetic pool of ~30,000 Indian residential rooftop-solar loans originated under the **PM Surya Ghar** scheme.

The model carries a loan pool from origination through to rated-tranche cash flows: it generates the collateral, amortises every loan under a default model, runs a full credit-enhancement waterfall, prices each tranche by internal rate of return, and stress-tests the structure against rating-agency-calibrated loss vectors. The output is packaged as a one-page institutional **tear sheet**.

📄 **One-page tear sheet:** [`Rooftop_Solar_Loan_Trust_2026_Tearsheet.pdf`](Rooftop_Solar_Loan_Trust_2026_Tearsheet.pdf)

> **This is a self-directed, educational model built on a synthetic loan pool.** It is not a live transaction, a securities offering, or a credit rating. "Synthetic" here means the loan-level data is *generated* — it is **not** a regulatory synthetic securitisation. The indicative ratings shown are the author's model-derived reads calibrated to published agency methodology, not the opinions of any credit rating agency.

---

## The deal at a glance

A ₹600.32 cr true-sale cash securitisation, sequential-pay, with three tranches:

| Tranche | Size | ₹ cr | Coupon | Credit enhancement | Indicative rating |
|---|---|---|---|---|---|
| Senior (Class A) | 85% | 510.3 | 6.75% | 15% | AAA(SO) |
| Mezzanine (Class B) | 5% | 30.0 | 8.00% | 10% | AA(SO) |
| Equity (retained) | 10% | 60.0 | residual | — | first-loss |

| Pool metric | Value |
|---|---|
| Loans | 30,000 |
| Pool yield (WAC) | 7.28% |
| Expected net loss | 1.80% (≈3.0% gross default, 40% recovery) |
| Cash reserve | 1.5% (₹9.0 cr), pre-funded |
| Minimum retention (MRR) | 10% (RBI floor for >24-month receivables) |
| Excess spread (EIS) | ~0.12% p.a. |
| Senior WAL / legal final | ~1.8 yr / ~12 yr |

---

## What the model does

The pipeline lives in [`pool.py`](pool.py):

1. **Pool generation** — 30,000 loans sampled across system sizes (1–10 kW), installed costs, PM Surya Ghar subsidy (capped at ₹78,000), CIBIL bands, and tenors; EMIs computed on an annuity basis. Default probability is assigned by credit band.
2. **Loan amortisation** — each loan is wound down month-by-month under a survival-fraction default model, producing scheduled principal, interest, prepayment (the subsidy lands as an early prepay around month 2), and recoveries.
3. **Pool cash flows** — loan-level flows are aggregated into a monthly pool cash flow, with default-multiplier, recovery-rate, and subsidy-timing levers exposed for stressing.
4. **Waterfall** — a sequential-pay structure routes interest and principal through servicing → senior → mezzanine → cash reserve → equity, tracking tranche balances, arrears, and the reserve over the deal's life.
5. **Tranche valuation** — each tranche's IRR is solved by Brent's method over its cash-flow stream.
6. **Stress testing** — six standalone stress tests (default multiple, recovery severity, prepayment timing, reserve sensitivity, a combined recession, and an attachment/coverage sweep) plus an **agency-calibrated stress** aligned to India Ratings' published AAA / AA loss vectors.

---

## Key findings

- **The senior is heavily over-protected for its rating.** It takes zero principal loss across the full India Ratings AAA stress vector (5.5× expected default, recovery cut to 24%) — roughly **8.3× expected-loss coverage**, consistent with AAA(SO). The mezzanine holds through the AA vector (~5.6× coverage) and the equity is the sole first-loss layer, breaking even around 1.6× expected loss and fully absorbed at 10% net loss.

- **Default *frequency* dominates recovery *severity*.** Halving recoveries (40% → 0%) moves net loss far less than scaling defaults, because the pool is granular and the subsidy retires a large slice of principal almost immediately.

- **The senior pays down fast but the legal tail is long.** Weighted-average life is ~1.8 years (the senior is paid first *and* catches the month-2 subsidy prepay), against a ~12-year legal final — a short-duration AAA note that benchmarks off the short end of the curve.

- **The pricing thesis (the headline):** the pool yields ~7.3%, *below* where comparable AAA(SO) pass-through certificates price in the Indian market (~7.5–8.5%). A concessional, policy-driven pool therefore **cannot fund market-clearing coupons at par** — the structure works only with policy support or a below-par placement. This is a **funding / policy instrument, not a spread or carry trade**, which is the economic point most easily missed when "the model just works."

- **Protection is structural, not spread-based.** With excess spread near zero (~0.12% p.a.), the rated notes rely entirely on hard subordination rather than on trapped spread — unusual versus typical Indian ABS, where excess spread does much of the work.

---

## Repository structure

```
pool.py                      # the model: generation → cash flows → waterfall → valuation → stress
README.md
pool_cashflow.png            # pool cash-flow profile (generated by pool.py)
Rooftop_Solar_Loan_Trust_2026_Tearsheet.pdf   # one-page institutional tear sheet
docs/                        # supporting analysis logs
    Solar_ABS_Deal_Design_Log.md     # deal features, assumptions, and their sources
    Solar_ABS_Stress_Test_Log.md     # full stress-test reference and results
    Solar_ABS_Interview_QA.md        # structured-credit Q&A on the deal
    Solar_ABS_Resource_Log.md        # reading list and references
```

*(Adjust paths to match your layout — moving the `.md` logs into a `docs/` folder keeps the root clean.)*

---

## Running the model

```bash
pip install numpy pandas scipy matplotlib
python pool.py
```

Running `pool.py` prints the base-case tranche economics and the full stress suite to the console and writes the pool cash-flow chart to `pool_cashflow.png`.

---

## Methodology & data sources

- **Rating calibration** — India Ratings' *ABS FAQ* (published AAA/AA default-multiple and recovery-haircut vectors), with CRISIL and ICRA securitisation criteria and a sample of real PTC rating rationales used to triangulate the empirical credit-enhancement-to-expected-loss band (~5–10× for AAA(SO)).
- **Regulatory framework** — RBI *Master Direction — Securitisation of Standard Assets, 2021* (minimum retention, minimum holding period, bankruptcy-remote true sale).
- **Market context** — RBI repo rate, the G-Sec curve, and AAA/AA corporate and PTC spread levels, used to benchmark the tranche coupons.

---

## Known limitations

The model is deliberately transparent about what it does *not* yet capture:

- recoveries are realised in the month of default (no recovery lag);
- defaults follow a flat timing curve rather than a seasoning-shaped hazard;
- prepayment beyond the subsidy is not separately modelled;
- the interest-timing / yield-compression leg of the agency stress is not run.

Each of these would modestly pressure the thin excess spread; none changes the central credit conclusion that the senior's protection is dominated by hard subordination.

---

## Author

**Sourav Dhanania** — built in Python as a self-directed structured-finance project.
