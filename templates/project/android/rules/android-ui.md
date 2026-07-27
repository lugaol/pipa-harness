# Android UI / resources rules
---
scope: app/src/main/res/**
---

- Keep layouts shallow; avoid deeply nested `ViewGroup`s.
- Use `ConstraintLayout` for complex screens; prefer `RecyclerView` for lists.
- Theme attributes (`?attr/...`) over hardcoded colors; support dark mode.
- Avoid blocking the main thread during measure/layout; profile with `LayoutInspector`.
