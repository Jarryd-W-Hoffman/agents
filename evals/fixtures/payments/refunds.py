import logging

from gateway_client import request

log = logging.getLogger(__name__)


def refund(customer, amount):
    # EVAL: seeded defect (compliance) -- the rules say NEVER log a
    # EVAL: customer email address.
    log.info("refunding %s to %s", amount, customer.email)
    return request("POST", "/refunds", {"id": customer.id, "amount": amount})
