# {{PROJECT_NAME}} — pipa harness extension

{{PROJECT_DESCRIPTION}}

This `.pipa/extension/` directory carries only project-specific context.
The base rules, skills, agents, and workflow come from the shared pipa_harness
install (wired into your runtime by `pipa init` / `pipa up`). Edit this file
with your project's facts; delete what you don't need.

## Golden rules
- [HARD] Never commit or push unless the user explicitly asks.
- [HARD] Heavy work (audio, sensors, image processing) belongs in native code or background threads; UI thread is for UI only.
- [HARD] Permissions must be requested at runtime and declared in `AndroidManifest.xml`.
- Prefer `ViewBinding` / `DataBinding` over `findViewById`.
- Target the latest stable SDK; keep `minSdk` compatibility explicit.

## Commands
- Build: `{{BUILD_COMMAND}}`
- Tests: `{{TEST_COMMAND}}`
- Device install: `./gradlew installDebug`
- Logs: `adb logcat -s <TAG>:D | tail -n 80`

## Routing (load ONLY when the trigger matches)
| Task involves...                          | Load                                       |
|-------------------------------------------|--------------------------------------------|
| NDK, JNI, C++, Oboe, audio DSP            | skills/android-ndk/SKILL.md                |
| XML layouts, Compose, theming, Views      | skills/android-ui/SKILL.md                 |
| Release build, signing, versioning, Play  | skills/android-release/SKILL.md            |
| Latency, glitches, underruns, audio     | skills/android-latency/SKILL.md            |

Base routing (graphify, debugging, code-review, performance, …) is already
loaded globally by pipa_harness. Path-scoped rules in `rules/` attach by
path glob (`app/src/main/cpp/**` → `android-ndk.md`, `app/src/main/res/**` → `android-ui.md`).

## Repo map
`app/src/main/java/` (Kotlin/Java sources) · `app/src/main/cpp/` (NDK) ·
`app/src/main/res/` (UI) · `app/build.gradle.kts` (module build) ·
`build.gradle.kts` (project build) · `gradle/libs.versions.toml` (catalog).
