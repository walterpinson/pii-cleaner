---
name: "Commit"
description: "Create git commits with Conventional Commits messages. Use when you want to commit staged or unstaged changes with well-formed, logically grouped commit messages."
argument-hint: "Optional: describe scope or any special instructions (e.g. 'feat scope only')"
agent: "agent"
tools: [execute]
---

Analyze the current git repository state and create one or more commits following the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0) specification. Work through staged changes first, then unstaged changes.

---

## Workflow

### Phase 1 — Staged Changes

1. Run `git diff --cached --stat` to check for staged changes.
2. If staged changes exist:
   - Run `git diff --cached` to read the full diff.
   - Apply the **Grouping Strategy** below to determine how many commits to create.
   - Present the proposed commit plan: list each group, its message, and the files it covers, in the order they will be committed.
   - For each group, create the commit using `git commit -m "<message>"`.
3. If no staged changes exist, skip to Phase 2.

### Phase 2 — Unstaged Changes

1. Run `git status --short` and `git diff --stat` to check for unstaged changes (including untracked files).
2. If unstaged changes exist:
   - Run `git diff` and `git status --short` to read the full diff and identify untracked files.
   - Apply the **Grouping Strategy** to determine logical groups.
   - Present the proposed commit plan: list each group, its message, and the files it covers, in the order they will be committed (dependencies first).
   - For each group:
     - Stage the relevant files: `git add <files>`
     - Create the commit: `git commit -m "<message>"`
3. If no unstaged changes exist, report that the working tree is clean.

### Phase 3 — Summary

After all commits are created, run `git log --oneline -10` and present the result so the user can verify.

---

## Grouping Strategy

### Single commit — use when:
- All changes belong to the same type **and** the same logical concern (e.g., all are bug fixes to one feature).
- The diff is small (< ~20 files) and cohesive.
- All changes are in the same module, package, or closely related files.

### Multiple commits — use when:
- Changes span more than one Conventional Commits type (e.g., a `feat` and a `fix` in the same working tree).
- Changes touch independent features or modules with no coupling.
- A mix of production code and configuration/tooling changes exists (separate tooling into `chore` or `build` commits).
- Breaking changes are present — these must always be isolated in their own commit so the footer is unambiguous.

### Grouping heuristics (in priority order):
1. **Type boundary** — never mix types in one commit (`feat` + `fix` = two commits).
2. **Scope boundary** — changes to `auth` and `payments` are separate commits even if both are `feat`.
3. **Layer boundary** — application logic, tests, docs, and CI config each belong in separate commits unless the change is trivially small.
4. **Breaking change boundary** — a breaking change is always its own commit with a `BREAKING CHANGE:` footer.
5. **When in doubt, split** — smaller, focused commits are always preferable to large mixed ones.

---

## Conventional Commits Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Rules
- **Subject line**: imperative mood, lowercase after the type, no trailing period, ≤ 72 characters.
- **Body**: wrap at 72 characters; explain *what* and *why*, not *how*.
- **Breaking change**: add `BREAKING CHANGE: <description>` in the footer, or append `!` after the type/scope.
- **Multiple footers**: each on its own line, in the format `Token: value` or `Token #value`.

### Types

| Type | When to use |
|------|-------------|
| `feat` | A new feature visible to users or consumers of the API |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `style` | Formatting, whitespace — no logic change |
| `refactor` | Code restructuring with no feature or bug change |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Build system or external dependency changes |
| `ci` | CI/CD configuration changes |
| `chore` | Maintenance tasks that don't fit elsewhere |
| `revert` | Reverts a previous commit |

### Breaking Change Syntax

Append `!` after the type/scope **and** add a `BREAKING CHANGE:` footer:

```
feat(auth)!: replace JWT with session cookies

BREAKING CHANGE: clients must clear stored JWT tokens; cookie-based session auth is now required
```

### Examples

```
feat(auth): add OAuth2 login via GitHub
```

```
fix(api): handle null response from payment gateway

Closes #482
```

```
feat(checkout)!: replace cart session with JWT token

BREAKING CHANGE: the `cart_id` cookie is no longer set; clients must
use the Authorization header with a JWT returned from POST /cart.
```

```
chore: upgrade eslint to v9 and fix lint warnings
```

```
docs(kits): add install instructions to README
```
