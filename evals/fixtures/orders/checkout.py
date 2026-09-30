from pricing import calculate_total


def checkout(order):
    return {"total": calculate_total(order), "status": "ok"}
