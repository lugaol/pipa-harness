---
name: release
description: "Create releases, version bumps, and changelogs. Triggers: release, version, tag, publish, changelog, semver, cut a release."
---
# Release workflow

Cut a versioned release following semver and the project's conventions.

## Step 1 — Determine version bump
- Read the git log since the last tag: `git describe --tags --abbrev=0` then `git log <tag>..HEAD`.
- Classify changes:
  - **MAJOR** (x.0.0): breaking changes / incompatible API changes.
  - **MINOR** (0.x.0): new features, backwards-compatible.
  - **PATCH** (0.0.x): bug fixes only.
- Propose the next version. If unsure whether something is breaking, ask the user.

## Step 2 — Update version files
- Find where the version lives: `package.json`, `Cargo.toml`, `pyproject.toml`,
  `build.gradle`, `VERSION`, etc. Use graphify/grep if unknown.
- Bump the version in ALL version files — keep them in sync.
- Update the changelog (`CHANGELOG.md`) with the notable changes grouped by Added/Changed/Fixed.

## Step 3 — Verify
- Run the full build + test suite. Release only from a green build.
- Confirm working tree is clean: `git status`.

## Step 4 — Tag (only when the user explicitly confirms)
- `git tag -a v<version> -m "<message>"`
- Never push tags or trigger publish pipelines unless the user explicitly asks.

## Notes
- If the project has no version file or changelog, say so and ask how the user wants to track versions.
- Check `vault/decisions/` for any release-policy notes before applying defaults.
