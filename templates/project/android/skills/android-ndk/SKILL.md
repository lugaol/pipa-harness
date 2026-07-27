# Android NDK skill
Load when: task involves NDK, JNI, C++, Oboe, audio DSP, native code.

- Native code lives under `app/src/main/cpp/`.
- Use `CMakeLists.txt` and `build.gradle.kts` `externalNativeBuild`.
- For audio: prefer Oboe; target 48 kHz; keep buffers in multiples of 192 frames.
- Profile native code with `simpleperf` or Android Studio CPU profiler.
- Always check `adb logcat` native crashes and tombstones.
