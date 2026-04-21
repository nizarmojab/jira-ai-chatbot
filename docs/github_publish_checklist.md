# GitHub Publish Checklist

Use this checklist before pushing the project to GitHub.

## Security

- Verify that `.env` is ignored by Git
- Keep only `.env.example` in the repository
- Rotate any Jira or OpenAI keys that were previously stored in tracked files
- Review hardcoded URLs, emails, account IDs, and company-specific identifiers

## Repository Presentation

- Update `README.md` with:
  - project purpose
  - architecture
  - setup steps
  - screenshots if available
- Keep `docs/architecture.md` and `docs/jira_setup.md` linked from the README
- Add a short repository description on GitHub after publishing

## Codebase Hygiene

- Exclude `venv/`, caches, and local editor folders through `.gitignore`
- Confirm that generated files and secrets are not staged
- Check for broken encoding in user-facing files if you want a cleaner public presentation

## First Git Commands

```bash
git init
git add .
git status
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```
