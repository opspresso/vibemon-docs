# VibeMon Docs compatibility mirror

The canonical source is [vibemon-web](https://github.com/opspresso/vibemon-web). This repository publishes a generated snapshot from `public/install/` to `docs/` so existing URLs keep working. `docs/CNAME` remains owned here.

Use [the setup guide](https://vibemon.io/docs) for installation and [Web's documentation](https://github.com/opspresso/vibemon-web/blob/main/docs/README.md) for API and architecture details. Tests, installer manifest generation, and source edits belong in Web.

## Update the snapshot

Commit the Web source, then run from its checkout:

```bash
node scripts/sync-legacy.mjs --kind docs --target ../vibemon-docs --fix
node scripts/sync-legacy.mjs --kind docs --target ../vibemon-docs
```

Review and commit `docs/` and `mirror-source.json` together. Verification requires the Web revision recorded in that metadata. Do not edit generated files or regenerate a separate manifest here.

## CI and publication

The snapshot workflow checks out the pinned Web commit and compares every published byte. Web is private: configure the repository Actions secret `VIBEMON_WEB_READ_TOKEN` with read-only `contents` access to `opspresso/vibemon-web`. The ordinary repository `GITHUB_TOKEN` cannot read another private repository. Missing access fails the comparison with an explicit setup message.

GitHub Pages continues to publish `docs/`. This change does not deploy Web, change DNS, archive this repository, or remove it. Keep the compatibility publication until an authorized domain cutover has been verified.
