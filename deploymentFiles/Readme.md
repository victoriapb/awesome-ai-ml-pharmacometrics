# Automation Setup Guide

This document walks you through automating the explorer site so it stays in sync with the source README at `victoriapb/awesome-ai-ml-pharmacometrics`.

---

## How it works

```
┌─────────────────────────────────────────┐
│  Private repo (victoriapb/awesome-...)  │
│                                         │
│  README.md updated on main              │
│         │                               │
│         ▼                               │
│  notify-explorer.yml fires              │
│  repository_dispatch ──────────────┐    │
└─────────────────────────────────────┘    │
                                           │
┌──────────────────────────────────────────▼──┐
│  Public repo (anuraag-saini/...explorer)    │
│                                             │
│  update-site.yml triggers                   │
│         │                                   │
│         ├── Fetches README via GitHub API    │
│         ├── Runs build_site.py              │
│         ├── Commits updated index.html      │
│         └── GitHub Pages auto-deploys       │
│                                             │
│  Also runs daily at 06:00 UTC as backup     │
└─────────────────────────────────────────────┘
```

Three triggers keep the site updated:
1. **Push trigger** — Private repo pushes README → dispatches event → public repo rebuilds (instant)
2. **Daily schedule** — Cron backup at 06:00 UTC in case dispatch is missed
3. **Manual** — Click "Run workflow" in the Actions tab anytime

---

## Step 1: Create a Personal Access Token (PAT)

You need **one** fine-grained PAT that covers both repos.

1. Go to https://github.com/settings/tokens?type=beta (Fine-grained tokens)
2. Click **Generate new token**
3. Settings:
   - **Name**: `ai-ml-pharmacometrics-automation`
   - **Expiration**: 90 days (or custom — you'll need to rotate it)
   - **Resource owner**: Your account (`anuraag-saini`)
   - **Repository access**: Select **"Only select repositories"**, then pick:
     - `anuraag-saini/awesome-ai-ml-pharmacometrics-explorer`
     - `victoriapb/awesome-ai-ml-pharmacometrics` *(you need collaborator access)*
   - **Permissions**:
     - **Contents**: Read (to fetch README from the private repo)
     - **Actions**: Read & Write (to trigger dispatches on the public repo, only needed if setting up the dispatch from the private repo)
4. Click **Generate token** and **copy it immediately**

> **Alternative — Classic PAT**: If the fine-grained approach doesn't work with the `victoriapb` org, create a classic token at https://github.com/settings/tokens with `repo` scope. It's broader but simpler.

---

## Step 2: Add the secret to the public explorer repo

1. Go to https://github.com/anuraag-saini/awesome-ai-ml-pharmacometrics-explorer/settings/secrets/actions
2. Click **New repository secret**
3. Name: `SOURCE_REPO_PAT`
4. Value: paste the PAT from Step 1
5. Click **Add secret**

---

## Step 3: Add files to the public explorer repo

Your repo should look like this:

```
awesome-ai-ml-pharmacometrics-explorer/
├── .github/
│   └── workflows/
│       └── update-site.yml      ← from this package
├── build_site.py                ← from this package
├── index.html                   ← auto-generated (and initial version)
└── README.md                    ← optional repo readme
```

Copy these files:
- `.github/workflows/update-site.yml`
- `build_site.py` (already in the repo from earlier)

Commit and push.

---

## Step 4 (Optional): Set up instant triggers from the private repo

This makes the explorer rebuild immediately when README.md changes, instead of waiting for the daily cron.

### If you have write access to the private repo:

1. Add the PAT as a secret in the **private** repo:
   - Go to `victoriapb/awesome-ai-ml-pharmacometrics` → Settings → Secrets → Actions
   - Name: `EXPLORER_DISPATCH_PAT`
   - Value: same PAT from Step 1
2. Copy `notify-explorer.yml` to the private repo at:
   ```
   .github/workflows/notify-explorer.yml
   ```
3. Commit and push

Now whenever `README.md` is pushed to main in the private repo, it will trigger the explorer to rebuild within seconds.

### If you don't have write access:

Skip this step. The daily cron at 06:00 UTC will keep things in sync with at most ~24h delay. You can always hit "Run workflow" manually in the Actions tab for an immediate update.

---

## Step 5: Test it

1. Go to https://github.com/anuraag-saini/awesome-ai-ml-pharmacometrics-explorer/actions
2. Click **"Update Explorer Site"** in the left sidebar
3. Click **"Run workflow"** → **"Run workflow"**
4. Watch it run — should take ~15 seconds
5. Check https://anuraag-saini.github.io/awesome-ai-ml-pharmacometrics-explorer/

---

## Maintenance

### Rotating the PAT
Fine-grained PATs expire. When yours does:
1. Generate a new one (same settings as Step 1)
2. Update the `SOURCE_REPO_PAT` secret in the public repo
3. Update `EXPLORER_DISPATCH_PAT` in the private repo (if using Step 4)

### Monitoring
- Check the Actions tab for failed runs
- GitHub sends email notifications for workflow failures by default
- The workflow summary shows paper count so you can spot parsing issues

### Updating the build script
If you add new methodology tags or application categories in `main.py`, the `build_site.py` parser will pick them up automatically since it reads whatever's in the README. No changes needed.
