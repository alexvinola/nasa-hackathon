---
name: github-workflow
description: Use when working with GitHub from the terminal - opening or updating a pull request, reading review comments, checking why an Actions run failed, or reading an issue. Uses the gh CLI with the developer's existing login.
---

# GitHub with `gh`

Use the actual PR/MR target branch, the user's specified base, or the repository's
configured default for a new change. Do not assume `develop`. Check whether the
CLI is installed before the authentication check. A missing login is a setup
issue for the developer, not permission to collect credentials.

## Before anything

```bash
gh auth status        # logged in? if not, ask the developer to run `gh auth login`
```

Never ask for or handle a token yourself.

## Pull requests

```bash
gh pr create --fill                         # title/body from the commits; add --draft while in progress
gh pr create --title "..." --body-file pr.md --base <target-branch>
gh pr view                                  # the PR for the current branch
gh pr view 123 --comments                   # PR conversation; inline review threads via API below
gh pr diff 123
gh pr checks 123                            # CI status per check
gh pr list --author @me --state open
```

Write the description from the actual diff: what changes, why, how it was
tested. Follow the user's authorization for external writes; do not ask again
when the action was explicitly requested.

## CI (Actions)

```bash
gh run list --branch "$(git branch --show-current)" --limit 5
gh run view <run-id>                        # jobs and their status
gh run view <run-id> --log-failed           # only the failing steps' logs
gh run rerun <run-id> --failed              # rerun the selected revision when authorized
```

Read the failing log before touching code: tell a real failure from a flaky or
infrastructure one.

## Issues

```bash
gh issue view 42 --comments
gh issue list --assignee @me
```

## Anything else

`gh api` calls the REST or GraphQL API with the same login, e.g.
`gh api repos/{owner}/{repo}/pulls/123/comments`.
