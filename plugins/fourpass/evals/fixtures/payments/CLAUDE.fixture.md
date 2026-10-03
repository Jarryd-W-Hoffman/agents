# Payments module rules

- **NEVER** write cardholder data or a customer's email address to logs, error
  messages, or analytics. Log the customer id only.
- All outbound HTTP MUST go through `gateway_client.request`; do not call
  `requests` or `urllib` directly from this module.
