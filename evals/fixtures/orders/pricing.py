def calculate_total(order):
    return sum(line.amount for line in order.lines)
