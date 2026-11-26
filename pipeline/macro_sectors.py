"""Definitions and reconciliation for MoSPI's sector breakdowns."""

GVA_GROUPS = {
    "gva_primary": ("gva_agriculture", "gva_mining"),
    "gva_secondary": ("gva_manufacturing", "gva_utilities", "gva_construction"),
    "gva_services": ("gva_trade", "gva_financial", "gva_public"),
}
GVA_COMPONENTS = tuple(sid for members in GVA_GROUPS.values() for sid in members)
IIP_COMPONENTS = ("iip_mining", "iip_manufacturing", "iip_electricity", "iip_water")


def gva_group_levels(levels):
    """Reconcile real GVA levels in ₹ crore and add the three broad-sector totals."""
    expected = set((*GVA_COMPONENTS, "gva_total"))
    grouped = {}
    for quarter, values in levels.items():
        missing = expected - values.keys()
        if missing:
            raise ValueError(f"{quarter}: missing GVA levels: {', '.join(sorted(missing))}")
        # Eight components and the total are independently rounded to ₹ crore.
        if abs(sum(values[sid] for sid in GVA_COMPONENTS) - values["gva_total"]) > 5:
            raise ValueError(f"{quarter}: GVA components do not reconcile to total GVA")
        grouped[quarter] = {**values, **{
            group: sum(values[sid] for sid in members) for group, members in GVA_GROUPS.items()
        }}
    return grouped


def gva_group_growth(levels):
    """Calculate year-on-year growth from reconciled broad-sector real GVA levels."""
    grouped = {group: [] for group in GVA_GROUPS}
    for quarter, current in sorted(levels.items()):
        prior = levels.get(f"{int(quarter[:4]) - 1}{quarter[4:]}")
        if prior is None:
            continue
        for group in GVA_GROUPS:
            this_year = current[group]
            last_year = prior[group]
            if last_year <= 0:
                raise ValueError(f"{quarter}: invalid prior-year GVA level for {group}")
            grouped[group].append((quarter, round((this_year / last_year - 1) * 100, 1)))
    return grouped
