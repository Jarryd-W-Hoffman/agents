from pricing import compute_total


def monthly_report(orders):
    # EVAL: seeded defect (completeness) -- compute_total was renamed to
    # EVAL: calculate_total and this call site was not updated.
    return sum(compute_total(o) for o in orders)
