# Change intent

Remove `customers.legacy_email`. It was superseded by `email` in the March
cutover and every customer now has `email` set.

- Drop the column.
- Stop reading it in `CustomerController::show` and writing it in `store`.
- Remove it from the model's fillable fields.
