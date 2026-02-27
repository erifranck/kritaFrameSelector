---
name: release
description: Guide through a versioned release of the Krita Frame Selector plugin. Builds the zip, tags the version, and pushes to GitHub.
argument-hint: "[major|minor|patch]"
---

# Release Skill — Krita Frame Selector

You are guiding the user through a release of the **Krita Frame Selector** Krita plugin.

## Step 1 — Detect the current version

Run this command and tell the user what the latest version tag is (or "no releases yet" if none):

```bash
git tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1
```

If no tags exist, treat the current version as `v0.0.0`.

## Step 2 — Ask for bump type

If the user did NOT pass an argument via `$ARGUMENTS`, ask:

> "What type of release is this?"
> - **major** — breaking changes or big new feature (e.g. v1.0.0 → v2.0.0)
> - **minor** — new feature, backwards compatible (e.g. v1.0.0 → v1.1.0)
> - **patch** — bug fix only (e.g. v1.0.0 → v1.0.1)

If the user DID pass an argument, use `$ARGUMENTS` as the bump type directly.

## Step 3 — Compute the new version

From the current version and the chosen bump type, compute the new version tag (format: `vMAJOR.MINOR.PATCH`). Show it to the user and ask:

> "The new version will be **vX.Y.Z**. Does that look right? (yes / no)"

If the user says no, ask them to type the version they want manually (must match `vX.Y.Z`).

## Step 4 — Check working tree

Run:

```bash
git status --short
```

If there are **uncommitted changes**, warn the user:

> "You have uncommitted changes. Do you want to commit them before releasing? (yes / no)"

If yes, ask: "What is the commit message?" then run:

```bash
git add .
git commit -m "<their message>"
```

## Step 5 — Push latest commits

Run:

```bash
git push origin main
```

Tell the user if this succeeded or show the error.

## Step 6 — Build the zip

Run:

```bash
chmod +x build_zip.sh && ./build_zip.sh frame_selector.zip
```

Confirm the zip was created successfully. If it fails, show the error and stop — do not continue to tagging.

## Step 7 — Tag and push

Run these two commands in order:

```bash
git tag <new-version>
git push origin <new-version>
```

## Step 8 — Summary

Tell the user:

> "Release **vX.Y.Z** is on its way!
>
> GitHub Actions will now:
> 1. Build the plugin zip
> 2. Create a GitHub Release at: https://github.com/erifranck/kritaFrameSelector/releases/tag/vX.Y.Z
> 3. Attach `frame_selector.zip` as a downloadable asset
>
> You can monitor progress at: https://github.com/erifranck/kritaFrameSelector/actions"