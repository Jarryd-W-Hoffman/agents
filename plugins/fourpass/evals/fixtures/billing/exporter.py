"""Invoice export. Customers are optional on API-created invoices."""


def export_row(invoice):
    # EVAL: seeded defect (correctness) -- invoice.customer is None for
    # EVAL: API-created invoices and .email is read without a guard.
    return f"{invoice.id},{invoice.customer.email},{invoice.total}"


def export_all(invoices):
    return [export_row(i) for i in invoices]
