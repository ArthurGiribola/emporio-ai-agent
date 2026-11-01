# Publication instructions (not executed)

Confirm the submission deadline and required GitHub/PDF/Forms format with the
recruiter first. Do not change or push the repository after the deadline. No
remote or submission was created during this work.

## Review locally

From this repository in PowerShell, before any remote creation:

```powershell
git status --short
git log --reverse --format="%h %s"
git log -1 --format=fuller
git ls-files
git remote -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Require a clean working tree and expected tests/skips. Review author/committer
metadata: one consistent personal Git identity is present and will be public.
The audit found no source customer records, credentials, CSVs, or restricted PDF
in history. Pattern scanning is not a guarantee against every possible secret.
Never add `data/`, private files, `.env`, virtual environments, or audit scratch
files. Do not upload a ZIP of the working directory. Preserve existing history;
do not amend old commits, squash, force-push, or manufacture development history.

## Create a private repository and inspect it

Install GitHub CLI, then run these commands only when ready to publish. The
example name is optional; use a new empty repository. If `origin` already exists,
inspect it and stop rather than overwriting it.

```powershell
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
$githubOwner = gh api user --jq .login
$repoName = "artefact-ai-customer-service"
gh repo create "$githubOwner/$repoName" --private --source . --remote origin
git remote -v
git push -u origin main
gh repo view "$githubOwner/$repoName" --web
```

The create command deliberately omits `--push`; inspect the target before the
separate push. Do not initialize a second README/license/history remotely. Review
all uploaded files, commit history, examples, and README while still private.
Only the committed history is pushed; ignored originals stay local.

## Make public when authorized and before the deadline

```powershell
gh repo edit "$githubOwner/$repoName" --visibility public --accept-visibility-change-consequences
gh repo view "$githubOwner/$repoName" --json url,visibility
```

Submit the displayed URL only using the confirmed delivery channel. If the
recruiter also requires an English PDF via Forms, prepare and verify that
separately; a GitHub URL alone does not resolve the conflicting instructions.
No paid API key is needed for the Ollama route.

Commands checked against the official [repository creation manual](https://cli.github.com/manual/gh_repo_create)
and [repository edit manual](https://cli.github.com/manual/gh_repo_edit) on November 1, 2026.
