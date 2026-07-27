# Android release skill
Load when: task involves release build, signing, versioning, Play Store, APK/AAB.

- Release builds use `gradlew assembleRelease` or `gradlew bundleRelease`.
- Store signing keystore credentials outside the repo; use env vars or `local.properties`.
- Bump version in `build.gradle.kts` (or `gradle/libs.versions.toml`) before release.
- Run `./gradlew lint` and `./gradlew test` before building release.
- Keep `minSdk`, `targetSdk`, and `compileSdk` aligned with the project baseline.
