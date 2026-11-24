"""
Derived banking measures for the "Bank credit and deposit growth" brief. Pure functions, no I/O.

Inputs are monthly series as {'YYYY-MM': value}. Outputs are sorted [('YYYY-MM', value), ...].

- growth_gap: credit growth minus deposit growth (y/y, percentage points).
- trailing_mean: average of the last n consecutive months; a month is skipped if any of its window is missing.
- incremental_cd_fytd: change in credit since end-March divided by the change in deposits since end-March,
  in per cent ("₹X of credit for every ₹100 of deposits"). Months are left out when deposits have grown by
  less than MIN_DEPOSIT_GROWTH of the end-March stock (or fallen), because the ratio is then unstable or
  meaningless. That is usually April and May.
"""

MIN_DEPOSIT_GROWTH = 0.005   # 0.5% of end-March deposits


def _prev_month(ym, k=1):
    y, m = int(ym[:4]), int(ym[5:7]) - k
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def growth_gap(credit_yoy, deposit_yoy):
    return [(p, credit_yoy[p] - deposit_yoy[p]) for p in sorted(credit_yoy) if p in deposit_yoy]


def trailing_mean(points, n=3):
    d = dict(points)
    out = []
    for p in sorted(d):
        window = [_prev_month(p, k) for k in range(n)]
        if all(w in d for w in window):
            out.append((p, sum(d[w] for w in window) / n))
    return out


def fiscal_base(ym):
    """End-March month that starts the Indian financial year containing `ym`."""
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y if m >= 4 else y - 1}-03"


def incremental_cd_fytd(credit, deposits, min_growth=MIN_DEPOSIT_GROWTH):
    out = []
    for p in sorted(credit):
        if p.endswith("-03") or p not in deposits:
            continue                                   # end-March itself is the base, not an observation
        base = fiscal_base(p)
        if base not in credit or base not in deposits:
            continue
        d_dep = deposits[p] - deposits[base]
        if d_dep < min_growth * deposits[base]:
            continue
        out.append((p, (credit[p] - credit[base]) / d_dep * 100))
    return out
