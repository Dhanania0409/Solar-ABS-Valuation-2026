# =========================================================
#  SOLAR ABS  —  Synthetic rooftop-solar loan pool
# =========================================================
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)     # seed -> reproducible pool
n_loans = 30000                     # change this to scale the pool


# ---------------------------------------------------------
#  BUILD  (Phase 1 + EMI)  — computation only, no printing
# ---------------------------------------------------------

# system size (kW) — residential PM Surya Ghar, 1–3 kW for now
capacity_choices = [1, 2, 3, 4, 5, 10]
capacity_weights = [0.15, 0.30, 0.35, 0.12, 0.05, 0.03]
capacities = rng.choice(capacity_choices, size=n_loans, p=capacity_weights)

# system cost — realistic size-banded ranges, sampled PER LOAN (not midpoints)
cost_low  = {1: 75000, 2: 150000, 3: 189000, 4: 252000, 5: 315000, 10: 630000}
cost_high = {1: 85000, 2: 170000, 3: 215000, 4: 285600, 5: 357000, 10: 714000}
low  = np.array([cost_low[k]  for k in capacities])
high = np.array([cost_high[k] for k in capacities])



system_cost = rng.uniform(low, high).round().astype(int)

# subsidy from size (unchanged): 1kW→30k, 2kW→60k, 3kW→78k, capped at 78k
subsidy = np.minimum(capacities, 2) * 30000 + np.clip(capacities - 2, 0, 1) * 18000
subsidy = np.minimum(subsidy, 78000)

# credit band
cibil_choices = ["750+", "700-749", "650-699"]
cibil_weights = [0.55, 0.30, 0.15]
cibil_band = rng.choice(cibil_choices, size=n_loans, p=cibil_weights)

# tenor (months)
tenor_choices = [120, 180]
tenor_weights = [0.80, 0.20]
tenor_months = rng.choice(tenor_choices, size=n_loans, p=tenor_weights)

# state
state_choices = ["Gujarat", "Maharashtra", "Uttar Pradesh", "Madhya Pradesh",
                 "West Bengal", "Rajasthan", "Tamil Nadu", "Other"]
state_weights = [0.22, 0.16, 0.14, 0.10, 0.08, 0.08, 0.07, 0.15]
state = rng.choice(state_choices, size=n_loans, p=state_weights)

# assemble the table
pool = pd.DataFrame({
    "loan_id": np.arange(1, n_loans + 1),
    "capacity_kw": capacities,
    "system_cost": system_cost,
    "subsidy": subsidy,
    "cibil_band": cibil_band,
    "tenor_months": tenor_months,
    "state": state,
})

# interest rate (PM Surya Ghar structure)
repo_rate = 0.0525
home_loan_rate = 0.085
pool["secured"] = pool["system_cost"] > 200000
pool["apr"] = np.where(pool["secured"], home_loan_rate, repo_rate + 0.0050)

# annual default rate (CDR) by credit band — better credit, fewer defaults
default_rate_by_cibil = {"750+": 0.0075, "700-749": 0.015, "650-699": 0.025}
pool["annual_default_rate"] = pool["cibil_band"].map(default_rate_by_cibil)

# monthly payment (EMI = annuity PMT)
monthly_rate = pool["apr"] / 12
n = pool["tenor_months"]
pool["emi"] = (
    pool["system_cost"] * monthly_rate * (1 + monthly_rate) ** n
    / ((1 + monthly_rate) ** n - 1)
)


# ---------------------------------------------------------
#  INSPECTION  —  delete the # to switch a block ON
# ---------------------------------------------------------

# ----- 1. pool preview -----
print(pool.head())

# ----- 2. pool summary -----
print("number of loans :", len(pool))
print("total pool size : Rs", round(pool["system_cost"].sum() / 1e7, 2), "cr")
print("average ticket  : Rs", round(pool["system_cost"].mean()))
print("percent secured :", round(pool["secured"].mean() * 100, 1), "%")

# ----- 3. pool yield -----
wac = (pool["apr"] * pool["system_cost"]).sum() / pool["system_cost"].sum()
print("simple avg rate :", round(pool["apr"].mean() * 100, 3), "%")
print("WA coupon (WAC) :", round(wac * 100, 3), "%")

# ----- 4. EMI preview -----
print(pool[["loan_id", "system_cost", "apr", "tenor_months", "emi"]].head())

# ----- 5. single-loan amortization schedule -----  (currently ON)
# ----- 5. amortize a SINGLE loan (subsidy prepayment + defaults) -----

def amortize_loan(balance, annual_rate, emi, subsidy_amt, annual_default_rate=0.0,
                  recovery_rate=0.40, subsidy_month=2, max_months=360):
    rate = annual_rate / 12
    mdr = 1 - (1 - annual_default_rate) ** (1 / 12)   # monthly default rate
    sf = 1.0                                          # surviving fraction (1.0 = all still paying)
    rows = []
    month = 0
    while balance > 0.01 and month < max_months:
        month += 1

        # 1. defaults hit the still-performing balance; those borrowers STOP paying
        default  = balance * sf * mdr
        recovery = default * recovery_rate
        sf      *= (1 - mdr)                 # fewer survivors from here on

        # 2. the scheduled amortization advances as if nobody defaulted
        interest_sched  = balance * rate
        principal_sched = min(emi - interest_sched, balance)
        balance        -= principal_sched

        # 3. subsidy prepayment at month 2 shortens the schedule
        prepay_sched = 0.0
        if month == subsidy_month:
            prepay_sched = min(subsidy_amt, balance)
            balance     -= prepay_sched

        # 4. actual cash = scheduled cash, but ONLY survivors pay it
        interest  = interest_sched  * sf
        principal = principal_sched * sf
        prepay    = prepay_sched    * sf

        rows.append({"month": month, "interest": interest, "principal": principal,
                     "prepay": prepay, "default": default, "recovery": recovery,
                     "balance": balance * sf})
    return pd.DataFrame(rows)


# ----- 6. POOL-LEVEL cash flow: run every loan, sum the cash by month -----
def build_pool_cashflows(pool, max_months=360, default_mult=1.0, recovery_rate=0.40, subsidy_month=2):
    interest  = np.zeros(max_months + 1)
    principal = np.zeros(max_months + 1)
    prepay    = np.zeros(max_months + 1)
    default   = np.zeros(max_months + 1)
    recovery  = np.zeros(max_months + 1)

    for _, loan in pool.iterrows():
        s = amortize_loan(loan["system_cost"], loan["apr"], loan["emi"], loan["subsidy"],
                          loan["annual_default_rate"] * default_mult,
                          recovery_rate=recovery_rate, subsidy_month=subsidy_month)
        m = s["month"].values
        interest[m]  += s["interest"].values
        principal[m] += s["principal"].values
        prepay[m]    += s["prepay"].values
        default[m]   += s["default"].values
        recovery[m]  += s["recovery"].values

    cf = pd.DataFrame({
        "month": np.arange(1, max_months + 1),
        "interest": interest[1:],
        "principal": principal[1:],
        "prepay": prepay[1:],
        "default": default[1:],
        "recovery": recovery[1:],
    })
    cf["total_cash"] = cf["interest"] + cf["principal"] + cf["prepay"] + cf["recovery"]
    cf = cf[cf["total_cash"] > 0].reset_index(drop=True)
    return cf

pool_cf = build_pool_cashflows(pool)
print("Total cash over deal (Rs cr):", round(pool_cf["total_cash"].sum() / 1e7, 2))
print("Total defaulted   (Rs cr):", round(pool_cf["default"].sum()   / 1e7, 2))
print("Total recovered   (Rs cr):", round(pool_cf["recovery"].sum()  / 1e7, 2))

print("Pool monthly cash flow (Rs crore):")
print((pool_cf.set_index("month")[["interest", "principal", "prepay",
                                    "default", "recovery", "total_cash"]] / 1e7).round(2).head(6))

# ----- 7. visualize the pool cash flow -----
# import matplotlib.pyplot as plt

# m = pool_cf["month"]
# plt.figure(figsize=(11, 5))
# plt.bar(m, pool_cf["interest"] / 1e7, label="interest")
# plt.bar(m, pool_cf["principal"] / 1e7, bottom=pool_cf["interest"] / 1e7, label="principal")
# plt.bar(m, pool_cf["prepay"] / 1e7,
#         bottom=(pool_cf["interest"] + pool_cf["principal"]) / 1e7, label="prepay (subsidy)")
# plt.xlabel("month")
# plt.ylabel("cash to pool (Rs crore)")
# plt.title("Pool monthly cash flow")
# plt.legend()
# plt.tight_layout()
# plt.savefig("pool_cashflow.png", dpi=120)
# plt.show()

# ----- 8. FULL WATERFALL: reserve + carry-forward + per-tranche cash flows -----
def run_waterfall(pool_cf, pool0, senior_pct=0.85, mezz_pct=0.05, equity_pct=0.10,
                  senior_coupon=0.0675, mezz_coupon=0.080, servicing_rate=0.010,
                  reserve_pct=0.015):
    bal_sen = senior_pct * pool0
    bal_mez = mezz_pct   * pool0
    bal_eqt = equity_pct * pool0
    reserve_target = reserve_pct * pool0
    reserve = reserve_target
    sen_arrears = 0.0
    mez_arrears = 0.0
    rows = []
    for _, r in pool_cf.iterrows():
        # ---- INTEREST LADDER ----
        avail_int = r["interest"]
        servicing = servicing_rate / 12 * (bal_sen + bal_mez + bal_eqt)
        cash = max(avail_int - servicing, 0.0)

        sen_owed = bal_sen * senior_coupon / 12 + sen_arrears
        sen_pc = min(sen_owed, cash);    cash    -= sen_pc; sen_owed -= sen_pc
        sen_pr = min(sen_owed, reserve); reserve -= sen_pr; sen_owed -= sen_pr
        sen_int_recv = sen_pc + sen_pr; sen_arrears = sen_owed

        mez_owed = bal_mez * mezz_coupon / 12 + mez_arrears
        mez_pc = min(mez_owed, cash);    cash    -= mez_pc; mez_owed -= mez_pc
        mez_pr = min(mez_owed, reserve); reserve -= mez_pr; mez_owed -= mez_pr
        mez_int_recv = mez_pc + mez_pr; mez_arrears = mez_owed

        replenish = min(reserve_target - reserve, cash); reserve += replenish; cash -= replenish
        excess_interest = cash

        # ---- PRINCIPAL LADDER ----
        p = r["principal"] + r["prepay"] + r["recovery"]
        pay_sen = min(bal_sen, p); bal_sen -= pay_sen; p -= pay_sen
        pay_mez = min(bal_mez, p); bal_mez -= pay_mez; p -= pay_mez
        pay_eqt = min(bal_eqt, p); bal_eqt -= pay_eqt; p -= pay_eqt

        # ---- each tranche's total cash flow this month (interest + principal) ----
        sen_cf = sen_int_recv + pay_sen
        mez_cf = mez_int_recv + pay_mez
        eqt_cf = excess_interest + pay_eqt

        rows.append({"month": r["month"], "servicing": servicing,
                     "reserve_draw": sen_pr + mez_pr, "replenish": replenish, "reserve_bal": reserve,
                     "sen_arrears": sen_arrears, "mez_arrears": mez_arrears,
                     "excess_interest": excess_interest,
                     "sen_cf": sen_cf, "mez_cf": mez_cf, "eqt_cf": eqt_cf,
                     "bal_sen": bal_sen, "bal_mez": bal_mez, "bal_eqt": bal_eqt})
    return pd.DataFrame(rows)

pool0 = pool["system_cost"].sum()
wf = run_waterfall(pool_cf, pool0)

# ----- 9. TRANCHE VALUATION: realized IRR (bought at par) -----
from scipy.optimize import brentq

def irr_annual(cfs):
    npv = lambda r: sum(c / (1 + r) ** t for t, c in enumerate(cfs))
    try:
        return brentq(npv, -0.9, 0.9) * 12     # nominal annual
    except ValueError:
        return float("nan")                    # tranche essentially wiped out

face = {"senior": 0.85 * pool0, "mezz": 0.05 * pool0, "equity": 0.10 * pool0}
col  = {"senior": "sen_cf", "mezz": "mez_cf", "equity": "eqt_cf"}

# print("--- TRANCHE VALUATION (bought at par, held to maturity) ---")
# for name in ["senior", "mezz", "equity"]:
#     cfs = [-face[name]] + list(wf[col[name]].values)
#     recv = sum(cfs[1:])
#     print(f"{name:7s} | invested {face[name]/1e7:7.2f} cr | received {recv/1e7:7.2f} cr | "
#           f"net {(recv-face[name])/1e7:+6.2f} cr | IRR {irr_annual(cfs)*100:+6.2f}%")
    
# ----- 10. STRESS HARNESS + TEST 1 (default multiplier sweep) -----
W   = {"senior": 0.85, "mezz": 0.05, "equity": 0.10}
COL = {"senior": "sen_cf", "mezz": "mez_cf", "equity": "eqt_cf"}

def stress_run(default_mult=1.0, recovery_rate=0.40, subsidy_month=2,
               reserve_pct=0.015, senior_coupon=0.0675, servicing_rate=0.010):
    cf = build_pool_cashflows(pool, default_mult=default_mult,
                              recovery_rate=recovery_rate, subsidy_month=subsidy_month)
    w  = run_waterfall(cf, pool0, senior_coupon=senior_coupon,
                       servicing_rate=servicing_rate, reserve_pct=reserve_pct)
    net_loss = cf["default"].sum() - cf["recovery"].sum()
    out = {"net_loss_pct": net_loss / pool0 * 100,
           "reserve_min": w["reserve_bal"].min() / 1e7,
           "arrears": (w["sen_arrears"].iloc[-1] + w["mez_arrears"].iloc[-1]) / 1e7}
    for name in ["senior", "mezz", "equity"]:
        cfs = [-W[name] * pool0] + list(w[COL[name]].values)
        out[name] = irr_annual(cfs) * 100
    return out

# print("\n=== TEST 1: DEFAULT MULTIPLIER SWEEP ===")
# print(f"{'mult':>5}{'net_loss%':>11}{'senior':>9}{'mezz':>9}{'equity':>9}{'res_min':>9}{'arrears':>9}")
# for mult in [1.0, 1.5, 2.0, 3.0, 4.0, 6.0]:
#     r = stress_run(default_mult=mult)
#     print(f"{mult:>5.1f}{r['net_loss_pct']:>11.2f}{r['senior']:>8.2f}%{r['mezz']:>8.2f}%"
#           f"{r['equity']:>8.2f}%{r['reserve_min']:>8.2f}{r['arrears']:>8.2f}")
    
# print("\n=== TEST 2: RECOVERY / LGD STRESS ===")
# print(f"{'recovery':>9}{'net_loss%':>11}{'senior':>9}{'mezz':>9}{'equity':>9}{'arrears':>9}")
# for rec in [0.40, 0.20, 0.0]:
#     r = stress_run(recovery_rate=rec)
#     print(f"{rec*100:>8.0f}%{r['net_loss_pct']:>11.2f}{r['senior']:>8.2f}%{r['mezz']:>8.2f}%"
#           f"{r['equity']:>8.2f}%{r['arrears']:>8.2f}")
    
# print("\n=== TEST 3: PREPAYMENT TIMING STRESS ===")
# print(f"{'prepay_mo':>10}{'net_loss%':>11}{'senior':>9}{'mezz':>9}{'equity':>9}{'res_min':>9}{'arrears':>9}")
# for sm in [2, 6, 12, 24,36]:
#     r = stress_run(subsidy_month=sm)
#     print(f"{sm:>10d}{r['net_loss_pct']:>11.2f}{r['senior']:>8.2f}%{r['mezz']:>8.2f}%"
#           f"{r['equity']:>8.2f}%{r['reserve_min']:>8.2f}{r['arrears']:>8.2f}")

# print("\n=== TEST 4: RESERVE SENSITIVITY (carry-forward) ===")
# print(f"{'defaults':>9}{'reserve':>9}{'res_min':>9}{'arrears':>9}{'equity':>9}")
# for mult in [1.0, 6.0]:
#     for rp in [0.015, 0.005, 0.0]:
#         r = stress_run(default_mult=mult, reserve_pct=rp)
#         print(f"{mult:>7.1f}x {rp*100:>6.1f}% {r['reserve_min']:>8.2f} {r['arrears']:>8.2f} {r['equity']:>7.2f}%")

# print("\n=== TEST 5: COMBINED RECESSION (defaults x2.5, recovery 20%, prepay mo 24) ===")
# base = stress_run()
# rec  = stress_run(default_mult=2.5, recovery_rate=0.20, subsidy_month=24)
# print(f"{'metric':>12}{'base':>10}{'recession':>12}")
# for k, lbl in [("net_loss_pct","net loss%"),("senior","senior%"),("mezz","mezz%"),
#                ("equity","equity%"),("reserve_min","res_min"),("arrears","arrears")]:
#     print(f"{lbl:>12}{base[k]:>10.2f}{rec[k]:>12.2f}")


# print("\n=== TEST 6: LOSS COVERAGE / TRANCHE ATTACHMENT ===")
# print(f"{'mult':>5}{'net_loss%':>11}{'eqt_wd%':>9}{'mez_wd%':>9}{'sen_wd%':>9}{'eqt_IRR':>9}")
# for mult in [1.0, 1.6, 4.0, 6.0, 6.5, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]:
#     cf = build_pool_cashflows(pool, default_mult=mult)
#     w  = run_waterfall(cf, pool0)
#     nl  = (cf["default"].sum() - cf["recovery"].sum()) / pool0 * 100
#     ewd = w["bal_eqt"].iloc[-1] / (0.10*pool0) * 100
#     mwd = w["bal_mez"].iloc[-1] / (0.05*pool0) * 100
#     swd = w["bal_sen"].iloc[-1] / (0.85*pool0) * 100
#     eirr = irr_annual([-0.10*pool0] + list(w["eqt_cf"].values)) * 100
#     print(f"{mult:>5.1f}{nl:>11.2f}{ewd:>9.1f}{mwd:>9.1f}{swd:>9.1f}{eirr:>8.1f}%")

# print("\n=== AGENCY-CALIBRATED STRESS (Ind-Ra Fig 23 vectors) ===")
# print(f"{'rating':>9}{'def_mult':>9}{'recov':>7}{'net%':>7}{'sen_wd%':>8}{'mez_wd%':>8}{'eqt_wd%':>8}{'senIRR':>8}{'mezIRR':>8}")
# scen = [
#     ("IND A",    3.0, 0.32),
#     ("IND AA",   4.0, 0.28),
#     ("AAA-low",  4.0, 0.24),
#     ("AAA-high", 5.5, 0.24),
# ]
# for name, dm, rec in scen:
#     cf = build_pool_cashflows(pool, default_mult=dm, recovery_rate=rec)
#     w  = run_waterfall(cf, pool0)
#     nl = (cf['default'].sum()-cf['recovery'].sum())/pool0*100
#     swd = w['bal_sen'].iloc[-1]/(0.85*pool0)*100
#     mwd = w['bal_mez'].iloc[-1]/(0.05*pool0)*100
#     ewd = w['bal_eqt'].iloc[-1]/(0.10*pool0)*100
#     sirr = irr_annual([-0.85*pool0]+list(w['sen_cf'].values))*100
#     mirr = irr_annual([-0.05*pool0]+list(w['mez_cf'].values))*100
#     print(f"{name:>9}{dm:>9.1f}{rec*100:>6.0f}%{nl:>7.2f}{swd:>8.1f}{mwd:>8.1f}{ewd:>8.1f}{sirr:>7.2f}%{mirr:>7.2f}%")
