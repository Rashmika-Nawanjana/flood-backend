Git Workflow for All Contributors

Read this before your first commit.
-----------------------------------------------------------------------------------------------------

1️⃣ Run setup before doing anything
bash scripts/setup-git-hooks.sh

This installs the required Git hooks (commit message validator, branch checks, etc.).
If you skip this, your commits may get rejected.

-----------------------------------------------------------------------------------------------------

2️⃣ Protected Branches

The following branches are protected and cannot be pushed to directly:

main → Production
stg → Staging
dev → Development

❌ Do NOT work on these branches.
❌ Do NOT push directly to these branches.
✔️ Only merge via Pull Requests.

-----------------------------------------------------------------------------------------------------

3️⃣ Create a new branch for every task

Use one of these formats:

feature/<short-name> — new features
fix/<short-name> — bug fixes
chore/<short-name> — tooling / configs / docs
refactor/<short-name> — internal code improvements
hotfix/<short-name> — urgent production-level fixes

Example:

git checkout dev
git pull
git checkout -b feature/add-alert-endpoint

-----------------------------------------------------------------------------------------------------

4️⃣ Commit message rules

Every commit must use this format:

type(scope optional): short description
Valid examples
fix: add git hooks and branch protection
feat(api): add alert endpoint
chore(ci): add staging pipeline step
refactor(service): simplify pricing logic

If your message does not follow this format,
❌ the commit will be blocked by the Git hook.

-----------------------------------------------------------------------------------------------------

5️⃣ Submitting your changes (always merge into dev first)

All work must go through the pipeline:

(feature|fix|chore) → dev → stg → main

Steps:

Push your branch
git push -u origin feature/add-alert-endpoint
Open a Pull Request (PR) into dev
Get reviews + ensure CI checks pass
Merge into dev
Promotion flow (done by leads/admin):
dev → stg
stg → main

-----------------------------------------------------------------------------------------------------

6️⃣ Quick command checklist
git checkout dev
git pull
# make your changes
git checkout -b feature/my-task
git add .
git commit -m "feat: short message"
git push -u origin feature/my-task