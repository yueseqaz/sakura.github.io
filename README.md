# Sakura Portfolio

A light, misty-blue portfolio for [@yueseqaz](https://github.com/yueseqaz).
Static HTML, CSS, and JavaScript; no frontend dependencies or build step.

## Preview

Open `index.html` directly, or run:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Visit http://127.0.0.1:4173. All images and scripts are served locally.

## Automatic GitHub Sync

The page never requests GitHub's API from a visitor's browser. Instead:

1. `scripts/sync_github.py` fetches the public profile, avatar, and all pages of
   owned public repositories from GitHub.
2. It merges metadata with `projects.config.json` and generates `data.json`,
   `assets/data.js`, and the local avatar. The script wrapper supports direct
   `file://` previews without fetch/CORS restrictions.
3. `.github/workflows/sync-github.yml` runs every six hours and on manual dispatch.
   It also runs after relevant source/config changes on the default branch.
4. Successful snapshots are committed back to the repository. A fetch/validation
   failure fails the workflow and keeps the last successful snapshot available.

**This workflow is not active in the local folder.** Push these files to a GitHub
repository's default branch and enable Actions. It uses the built-in
`GITHUB_TOKEN`; no personal token is required. Allow Actions write permissions
if repository/organization policy restricts them. Branch protections may require
an alternative PR-based update process. Scheduled runs can be delayed by GitHub.

On GitHub: Actions → Sync GitHub portfolio → Run workflow.

To refresh locally with Python 3.9+:

```sh
python3 scripts/sync_github.py
python3 scripts/sync_github.py --check
```

Anonymous requests are rate-limited. Set `GITHUB_TOKEN` in your shell environment
if necessary; never put tokens in frontend files, config, URLs, or commits.
`--check` fetches and validates without writing files.

## Customize Projects

Edit `projects.config.json`, then sync:

- `username`: GitHub account to read.
- `exclude`: repository names to hide (case-insensitive). The profile/config and
  site-deployment repositories are excluded by default.
- `includeForks` / `includeArchived`: false by default. Private repos are excluded.
- `order`: curated repository order. New projects follow, sorted newest first.
- `overrides`: optional per-repository fields: `name`, `description`, `category`
  (`mac`, `dev`, `lab`), `tags`, `icon`, `badge`, `website`, or `hidden`.

Link priority: **manual website → GitHub Website → repository**.
Set `website` to `null` to explicitly disable the official site link. Each card's
GitHub icon always opens the source repository. Only HTTP(S) URLs are accepted.

Profile, stars, source language, and update time follow GitHub. Curated names,
descriptions, tags, classifications, ordering, and websites are preserved. New
repositories are included automatically; absent overrides, classification and
tags use the language/metadata. Deleted or renamed repositories disappear from
the next successful snapshot; update overrides after renames.

Do not edit generated data files manually. The initial snapshot is from the
previous successful repository lookup. Its displayed timestamp is the data's
snapshot time, not the visitor's current time.

## Deployment

For Vercel or another Git-connected static host, use this folder as the site root
with no build command. Ensure its Git integration redeploys snapshot commits.
If your host ignores automated commits, connect a deploy hook or add a deployment
step to this workflow; committing data alone cannot update an existing live site.

For GitHub Pages, this workflow includes an optional deployment job:

1. Repository Settings → Pages → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → Variables: set
   `DEPLOY_GITHUB_PAGES` to `true`.
3. Run **Sync GitHub portfolio** manually once. The same run syncs and deploys.

The optional Pages job uploads root HTML pages, `data.json`, and `assets/`, keeping
the existing product pages available alongside the new portfolio.
Do not rely on branch-based Pages builds being triggered by `GITHUB_TOKEN`
commits; the deployment job handles this explicitly.

Existing product sites point to `sakura-github-io.vercel.app`. Their original HTML
pages are preserved from the remote repository. If these product URLs move,
update the website overrides before the next sync.

## Tests

```sh
python3 -m unittest discover -s tests -v
node --check assets/app.js
node --check assets/data.js
```

Tests cover link priority, overrides, new projects, exclusions, pagination, API
failures, snapshot preservation, URL safety, and generated data consistency.
