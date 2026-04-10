🚀 Git Workflow for All Contributors

Read this before your first commit.

------------------------------------------------------------------------------------------------------

1️⃣ Run setup before doing anything

Install Git hooks:

bash scripts/setup-git-hooks.sh

These hooks enforce:

Commit message format
Branch naming rules
Protected branch restrictions

If you skip this step ⇒ your commits may be rejected.

------------------------------------------------------------------------------------------------------

2️⃣ Protected Branches

The following branches are protected:

| Branch | Purpose    |
|--------|------------|
| main   | Production |
| stg    | Staging    |
| dev    | Development |
❌ You must NOT:
Push directly to these branches
Commit on these branches
Merge without a Pull Request
✔️ You MUST:
Create a new branch
Submit a PR into dev

------------------------------------------------------------------------------------------------------

3️⃣ Create a new branch for every task

Use these naming patterns:

| Type              | Usage                           |
|-------------------|---------------------------------|
| feature/\<name\>  | New features                    |
| fix/\<name\>      | Bug fixes                       |
| chore/\<name\>    | Tooling, configs, documentation |
| refactor/\<name\> | Code cleanup / internal changes |
| hotfix/\<name\>   | Urgent production fixes         |

**Example:**

```bash
git checkout dev
git pull
git checkout -b feature/add-alert-endpoint
```

------------------------------------------------------------------------------------------------------

4️⃣ Commit Message Rules (Enforced by Git Hook)

Format:

type(scope optional): short description
Valid examples:
fix: add git hooks and branch protection
feat(api): add alert endpoint
chore(ci): add staging pipeline step
refactor(service): simplify pricing logic
❌ Invalid messages will be blocked.

The hook will reject commits that don’t follow the format.

------------------------------------------------------------------------------------------------------

5️⃣ Submitting Your Changes

All work goes to dev first.

Workflow:
(feature|fix|chore|refactor) → dev → stg → main
Steps:
Push your branch:
git push -u origin feature/add-alert-endpoint
Open a Pull Request into dev
Get a review + pass CI checks
Merge into dev
Promotion flow (done by leads/admins only)
dev → stg
stg → main

------------------------------------------------------------------------------------------------------

6️⃣ Quick Command Checklist
git checkout dev
git pull

# make your changes

git checkout -b feature/my-task
git add .
git commit -m "feat: short message"
git push -u origin feature/my-task
✅ Final Notes
Always keep dev updated before creating new branches.
Never merge without a PR.
Never commit directly to protected branches.
Commit messages MUST follow the enforced format.