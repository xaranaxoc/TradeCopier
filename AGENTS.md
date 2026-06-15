# AGENTS.md

Working rules for any AI coding agent (Claude Code, Cursor, Viktor, etc.) and for
humans working in this repository. Merge with task-specific instructions as needed.

---

## 0a. UI Polish workflow — single branch, commit per phase

The `feat/ui-polish` branch carries the multi-phase UI redesign that builds on
top of `feat/ctk-redesign`. Rules for this series specifically:

- **One branch, many commits.** Don't open a separate PR for every phase —
  push commits to `feat/ui-polish` and roll everything into one final PR
  when the series ends (or open one when ready to review).
- **One phase = one focused commit.** Each phase has a clear scope (design
  tokens, layout/DPI, components, tables, KPI polish, settings). The commit
  message names the phase, e.g. `feat(ui): phase 1 — design tokens + Inter + DPI`.
- **Don't touch business logic.** Only render layer and styling.
- **Bundled assets live in `img/fonts/`** (Inter, Phosphor, etc.) with a
  `LICENSES.md` next to them.
- **Each phase keeps the app launchable.** Run a smoke pass before committing.
- **Accent presets (Phase 6).** User-selectable accent lives in
  `config.json` under `preferences.accent` (cyan / teal / violet / amber).
  Applied at startup by `theme.apply_preferences_from_file(CONFIG_FILE)`
  which mutates `theme.ACCENT/ACCENT_HOVER/ACCENT_DIM/ACCENT_GLOW` *before*
  the `gui.py` module-level aliases bind to them. If you add a new alias,
  put it AFTER the `theme.apply_preferences_from_file(...)` call.

## 0. Commit Discipline — Checkpoint Every Step

**Commit after every step so you always have a checkpoint to roll back to.**

The goal: if something breaks, you can return to the last working state instead of
losing progress.

- **One logical step = one commit.** Make small, atomic commits. Don't bundle
  unrelated changes together.
- **Commit as soon as a step works.** Each commit should leave the code in a
  consistent, ideally working state.
- **Write clear messages.** Describe what the step did, e.g.
  `feat(copier): add reconnect on socket drop` or `fix(gui): correct lot-size rounding`.
- **Before any risky or large change, make sure the previous step is committed.**
  That commit is your checkpoint.
- **Push regularly** so checkpoints are backed up remotely, not just local.

To return to a checkpoint:

```bash
git log --oneline           # find the good commit hash
git revert <hash>           # safe: undoes a commit with a new commit (preferred on shared branches)
git reset --hard <hash>     # hard rollback: discards everything after <hash> (local/unpushed only)
```

Prefer `git revert` on branches others may have pulled. Use `git reset --hard` only on
your own local, unpushed work.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work")
require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites
due to overcomplication, and clarifying questions come before implementation rather than
after mistakes.

---

> Sections 1–4 are adapted from the MIT-licensed
> [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) project,
> derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876)
> on common LLM coding pitfalls.
