# Repository guidelines

This repository is a compatibility publishing mirror. `mirror-source.json` identifies the canonical `opspresso/vibemon-web` commit. Make source, test, and tooling changes there; copy generated content here with Web's `scripts/sync-legacy.mjs`.

`docs/` is generated except `docs/CNAME`. Preserve the CNAME and existing public paths. Update generated content and metadata together, then run the canonical comparison before committing. Keep root README and this guidance concise. `CLAUDE.md` links here.

Use Conventional Commits. PRs must identify the source revision, compatibility checks, and any required deployment configuration. Never commit credentials. Repository deletion, archival, production publication, and main-branch merges are separate authorized actions.
