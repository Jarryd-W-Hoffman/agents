# Conventions

- Repositories are named `<Thing>Repository` and expose `find_by_*`.
- **Exception:** append-only audit tables have no lookup API by design. They
  expose `append` only, and are named `<Thing>Log`. Do not add `find_by_*`
  to them.
