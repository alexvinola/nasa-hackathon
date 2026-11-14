# G7 · Forensic intro

Owner: FS3 · Branch: `goal/G7-forensic-intro` · Depends on: G6 · Budget: 4 h max

## Goal
Black-box animation (red alert → 48 h → 24 h → 2 h → the error) built with Framer Motion and the HUD components, no 3D engine.

## Done when
- The whole sequence plays on its own, in order, and ends on the "Rewind 48 h with S.Y.N.A.P.S.E." button.
- Clicking the button opens the live HUD.
- If the 4 h run out: static storyboard with voice-over, and this same test still applies.

## Check
`make check-G7` → `frontend/e2e/acceptance/g7-intro.spec.ts` (Playwright; each step has `data-step`).
