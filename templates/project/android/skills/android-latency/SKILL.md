# Android latency / performance skill
Load when: task involves latency, glitches, underruns, xruns, audio thread, performance.

- Audio callback must never block; do not allocate memory or lock in the callback.
- Use `AudioRecord`/`AudioTrack` or Oboe with high-priority mode.
- Profile with `systrace` and Android Studio CPU profiler.
- Target < 20 ms end-to-end latency for real-time audio/gesture apps.
- Log with `adb logcat` and always tail the last 80 lines.
