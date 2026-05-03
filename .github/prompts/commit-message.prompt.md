---
name: "Commit Message"
description: "Generate Conventional Commits message(s) from current git changes — staged files first, or all changes grouped into logical commits for copy/paste"
argument-hint: "Optional scope or context hint (e.g. 'auth module')"
agent: "agent"
tools: [execute]
---

# Generate Commit Message

Analyze the current git changes and generate commit message(s) following the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification. Output messages formatted for copy/paste — do not make any commits.

---

## Step 1 — Check for Staged Changes

Run:

```sh
git diff --cached --name-only
```

- If the output lists one or more files → proceed to **Step 2A**.
- If the output is empty → proceed to **Step 2B**.

---

## Step 2A — Staged Files Exist

Run:

```sh
git diff --cached
```

Generate a **single commit message** covering only the staged changes.

Output exactly this structure:

```
COMMIT MESSAGE
──────────────
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]

FILES TO COMMIT
───────────────
- path/to/staged-file.ext
- path/to/other-staged-file.ext

EXPLANATION
───────────
Brief rationale for why these files belong in one commit.
```

---

## Step 2B — No Staged Files

Run:

```sh
git diff
git status --short
```

Review all changes — including untracked files shown by `git status --short` — and group them into **logical commits** using the grouping strategy below. For each group, output one block:

```
── COMMIT 1 ─────────────────────────────────────────────────
COMMIT MESSAGE
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]

FILES TO INCLUDE
- path/to/file.ext

EXPLANATION
Brief rationale for this grouping.

── COMMIT 2 ─────────────────────────────────────────────────
COMMIT MESSAGE
...
```

After all groups, add a **Suggested Commit Order** list — list groups by number in the order they should be committed (dependencies first).

---

## Conventional Commits Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Rules**

- Subject line: ≤ 72 characters, lowercase, imperative mood, no trailing period
- Scope is optional and goes in parentheses: `feat(auth):`
- Append `!` after type/scope to signal a breaking change: `feat(api)!:`
- A `BREAKING CHANGE:` footer is required whenever `!` is used
- Separate subject, body, and footers with a blank line
- Body: wrap at 72 characters; explain *what* and *why*, not *how*
- Multiple footers: each on its own line, in the format `Token: value` or `Token #value`

---

## Common Conventional Commit Types

| Type | Use When |
|------|----------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `style` | Formatting, whitespace — no logic change |
| `refactor` | Code restructure without feature or fix |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system or dependency changes |
| `ci` | CI/CD configuration changes |
| `chore` | Maintenance tasks, tooling |
| `revert` | Reverting a previous commit |

---

## Breaking Change Syntax

Use `!` after the type/scope **and** add a `BREAKING CHANGE:` footer:

```
feat(auth)!: replace JWT with session cookies

BREAKING CHANGE: clients must clear stored JWT tokens; cookie-based session auth is now required
```

---

## Grouping Strategy (Step 2B Only)

### Single commit — use when:
- All changes belong to the same type **and** the same logical concern.
- The diff is small (< ~20 files) and cohesive.
- All changes are in the same module, package, or closely related files.

### Multiple commits — use when:
- Changes span more than one Conventional Commits type (e.g., a `feat` and a `fix`).
- Changes touch independent features or modules with no coupling.
- A mix of production code and configuration/tooling changes exists (separate tooling into `chore` or `build` commits).
- Breaking changes are present — these must always be isolated in their own commit.

### Heuristics (in priority order):
1. **Type boundary** — never mix types in one commit (`feat` + `fix` = two commits)
2. **Scope boundary** — changes to `auth` and `payments` are separate commits even if both are `feat`
3. **Layer boundary** — application logic, tests, docs, and CI config each belong in separate commits unless the change is trivially small
4. **Breaking change boundary** — a breaking change is always its own commit with a `BREAKING CHANGE:` footer
5. **When in doubt, split** — smaller, focused commits are always preferable to large mixed ones

---

## Examples

**Single feature with tests**

```
COMMIT MESSAGE
──────────────
feat(auth): add OAuth2 login flow

Implements authorization code flow with PKCE.
Supports GitHub and Google providers.

FILES TO COMMIT
───────────────
- src/auth/oauth.ts
- src/auth/providers/github.ts
- src/auth/providers/google.ts
- tests/auth/oauth.test.ts

EXPLANATION
───────────
All files implement the same feature unit. Tests are tightly coupled to the
implementation and ship together.
```

**Bug fix**

```
COMMIT MESSAGE
──────────────
fix(api): handle null response from user service

FILES TO COMMIT
───────────────
- src/api/users.ts

EXPLANATION
───────────
Single-file fix; no related changes belong with it.
```

**Breaking change**

```
COMMIT MESSAGE
──────────────
feat(config)!: replace JSON config with TOML

BREAKING CHANGE: rename config.json to config.toml and update all config
loader references; see docs/migration.md for details.

FILES TO COMMIT
───────────────
- config.toml
- config.json  (deleted)
- src/config/loader.ts
- docs/migration.md

EXPLANATION
───────────
Breaking format change isolated into its own commit so it is clearly
identifiable in history and easy to revert or bisect.
```

**Documentation only**

```
COMMIT MESSAGE
──────────────
docs: update README with kit naming convention

FILES TO COMMIT
───────────────
- README.md
- kits/README.md

EXPLANATION
───────────
Documentation-only changes with no code impact; grouped together.
```

**Maintenance / tooling**

```
COMMIT MESSAGE
──────────────
chore: upgrade eslint to v9 and fix lint warnings

FILES TO COMMIT
───────────────
- .eslintrc.json
- package.json
- package-lock.json

EXPLANATION
───────────
Tooling-only upgrade with no production code change; isolated as chore.
```

**Docs with scope**

```
COMMIT MESSAGE
──────────────
docs(kits): add install instructions to README

FILES TO COMMIT
───────────────
- kits/README.md

EXPLANATION
───────────
Documentation-only change scoped to the kits module.
```
