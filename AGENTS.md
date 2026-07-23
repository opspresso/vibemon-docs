# Repository Guidelines

## Project Structure & Module Organization

This repository publishes the VibeMon documentation site and installable integration files.

- `docs/` is the deployable site root. It contains `index.html`, setup documentation, the installer, example configuration, and platform-specific integrations for Claude Code, Codex, Kiro, and OpenClaw.
- `docs/vibemon/` holds shared Python runtime modules used by the integrations.
- `test/` contains the Python test suite, organized by the module under test.
- `scripts/generate_manifest.py` rebuilds `docs/manifest.json`, which records SHA-256 hashes for installed files.
- `.github/workflows/` contains repository automation.

Keep platform adapters thin and place reusable behavior in `docs/vibemon/`.

## Build, Test, and Development Commands

The project has no build step or third-party Python dependency installation.

- `python3 -m unittest discover -s test` runs the complete test suite.
- `python3 -m unittest test.test_install` runs one test module while iterating.
- `python3 scripts/generate_manifest.py` regenerates file hashes after changing installer-managed files.
- `python3 docs/install.py` exercises the local interactive installer; review prompts carefully because it writes user configuration.

Before submitting, run the full tests and confirm `git diff -- docs/manifest.json` is expected.

## Coding Style & Naming Conventions

Use Python 3 with four-space indentation and standard-library solutions where practical. Follow existing PEP 8-style naming: `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for constants, and `PascalCase` for test classes. Preserve the established formatting of JSON, TOML, JavaScript, and HTML files; no repository-wide formatter is configured. Keep comments focused on current behavior rather than change history.

## Testing Guidelines

Tests use Python's `unittest` framework. Name files `test_<module>.py`, classes `<Behavior>Test`, and methods `test_<expected_behavior>`. Add focused regression coverage for behavior changes. Tests must be isolated and must not depend on live services or a user's real configuration. There is no fixed coverage threshold, but new paths should cover success and relevant failure cases.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `ci:`, and `chore:`. Write concise, imperative subjects and keep each commit to one purpose.

Pull requests should explain the user-visible effect, list validation commands, and link related issues. Include screenshots for rendered site changes and sample payloads or configuration snippets when integration behavior changes. Regenerate `docs/manifest.json` whenever a manifest-managed file changes.

## Security & Configuration

Never commit API tokens, credentials, or personal configuration. Use placeholders in examples. Installer changes must preserve existing user settings and avoid silently overwriting configuration.
