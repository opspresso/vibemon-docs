# VibeMon Docs compatibility mirror

This repository publishes a generated snapshot of `vibemon-web/public/install/` to `docs/`. It preserves existing download URLs; `docs/CNAME` remains owned here.

## Find the right guide

- [VibeMon documentation](https://vibemon.io/docs) — Login, tokens, resources, coding accounts, and Desktop connection.
- [Hook installation](https://vibemon.io/docs/setup) — Install, configure, verify, and repair hooks.
- [Monitoring API](https://vibemon.io/docs/api/monitoring) — Cloud authentication and data contracts.
- [Desktop documentation](https://github.com/opspresso/vibemon-app/blob/main/docs/README.md) — App behavior, local API, and packaging.

## Maintain this mirror

The canonical source is [vibemon-web](https://github.com/opspresso/vibemon-web), a private maintainer repository. Source edits, tests, and generated-content changes belong there. Repository access is required to update or verify this mirror; reading the public guides does not require that access.

### Update the snapshot

Commit the Web source, then run from its checkout:

```bash
node scripts/sync-legacy.mjs --kind docs --target ../vibemon-docs --fix
node scripts/sync-legacy.mjs --kind docs --target ../vibemon-docs
```

Review and commit `docs/` and `mirror-source.json` together. Verification requires the Web revision recorded in that metadata. Do not edit generated files or regenerate a separate manifest here.

## CI and publication

The snapshot workflow checks out the pinned Web commit and compares every published byte. Web is private: configure the repository Actions secret `VIBEMON_WEB_READ_TOKEN` with read-only `contents` access to `opspresso/vibemon-web`. The ordinary repository `GITHUB_TOKEN` cannot read another private repository. Missing access fails the comparison with an explicit setup message.

GitHub Pages continues to publish `docs/`. This change does not deploy Web, change DNS, archive this repository, or remove it. Keep the compatibility publication until an authorized domain cutover has been verified.
