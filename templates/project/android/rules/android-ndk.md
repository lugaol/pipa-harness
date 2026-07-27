# Android NDK / native rules
---
scope: app/src/main/cpp/**
---

- Native code must be C/C++ only; keep Java/Kotlin as a thin UI/lifecycle layer.
- Use CMake for native builds (`externalNativeBuild.cmake`).
- Log native crashes via `__android_log_assert` and capture tombstones with `adb logcat -s DEBUG`.
- Prefer `AAssetManager` for bundled assets; never hardcode `/sdcard` paths.
