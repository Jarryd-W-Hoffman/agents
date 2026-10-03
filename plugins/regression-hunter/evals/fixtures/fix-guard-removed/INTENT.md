# Change intent

Move payment recording out of the Stripe webhook controller into a
`PaymentRecorder` service, so the admin "record a manual payment" screen can
reuse it. No behaviour change intended.
