# HS-005: A swallowed error that renders as a real number is worse than a crash

- 2026-10-03 (dashboard spend): `data/spend.py` passed the ledger path as a
  `str` where `pipa.spend.summarize` expects a `Path`. The resulting
  `AttributeError` was caught by a broad `except` and returned an all-zero
  summary — so the Spend tab read **0 rows, $0.00 against a 346-row ledger**,
  and nothing looked broken. Return the error alongside the zeros, or raise.
- 2026-10-03 (eval gate): the runner computed `failed` by iterating only
  values that were dicts, so every boolean check was silently dropped. It
  reported `0 failures` while all 9 agents violated the contract. A check that
  aggregates heterogeneous shapes will skip the shapes it does not know.
- Rule: `except: return empty` is only safe when empty is indistinguishable
  from healthy. For a number, a count, or a list the user reads as data, say
  "unknown" instead of "zero".
- Context: both were visible only by asking a question the UI does not ask.
