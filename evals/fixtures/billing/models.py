class Invoice:
    def __init__(self, id, total, customer=None):
        self.id = id
        self.total = total
        self.customer = customer


class Customer:
    def __init__(self, email):
        self.email = email
