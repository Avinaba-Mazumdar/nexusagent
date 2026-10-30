# Standards (what good output looks like)

## Code

- Engineering principles (SOLID, KISS, YAGNI, DRY) are defined in `00-identity.md`. Do not restate them here.
- No commented-out code. Git remembers.
- No dead code, no unused imports, no TODO without an owner and a date.
- Errors are handled, not swallowed. `catch {}` is a bug.

## Security baseline

The threat model, OWASP mapping, upload pipeline, and parameterization rules live in `architecture.md` §12 — read them there, do not restate them here. This checklist confirms security is satisfied per change:

- [ ] All user input validated and sanitized at the boundary.
- [ ] No secrets in code, logs, error responses, or client bundles. Server-only variables are listed in `architecture.md` §2.
- [ ] Auth checks on every protected route AND every protected API call — not just the UI.
- [ ] Dependencies: `pnpm audit` shows no unresolved high or critical advisories.
- [ ] CORS, CSP, and security headers are set explicitly for production.
- [ ] Every write carries an idempotency key, so a retry cannot double-charge.

## UI baseline

Visual numbers are defined once, in `design.md`. This list only names which properties to confirm.

- [ ] Empty state exists and is useful (says what to do next).
- [ ] Loading state exists (skeleton or spinner — never a blank screen).
- [ ] Error state exists and is recoverable (retry / back / contact).
- [ ] Keyboard navigable end-to-end. Focus is visible.
- [ ] Works at 360px width and at 1440px width.
- [ ] `prefers-reduced-motion` respected for any animation.
- [ ] Contrast, touch targets, and focus match `.agents/specs/design.md` (including its 4.5:1 normal-text contrast requirement).

Launch regression gates are Phase 12 in `.agents/specs/versions.md`. They are not required to close an earlier phase.

## Definition of done

1. The change matches the owning spec. Schema questions use `architecture.md`. Visual questions use `design.md`. Behavior questions use `features.md`.
2. From Phase 1 onward, the change has a test for the happy path and one failure path.
3. `pnpm typecheck` and `pnpm lint` pass with zero errors and zero warnings.
4. The security and UI checklists above are checked for the surfaces this change touches.
5. Implementation changes get one `.agents/brain.md` entry. Spec-only edits do not.
6. The commit message follows `.agents/rules/01-guides.md`.
7. Anything that must survive a handover to a gym owner exists in a spec, not only in this file.
