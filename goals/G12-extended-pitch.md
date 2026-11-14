# G12 · Pitch landing and extended edition (optional)

Owner: Everyone · Branch: `goal/G12-extended-pitch` · Depends on: G0 (`shared/sources.json`), G8 (the timed pitch it
must not slow down) · Optional: yes

## Goal
One file, `docs/brand/pulsar-intro.html`, with two editions. The **landing** is today's timed pitch for the live
presentation: short headlines and the real demo, nothing more. The **extended edition** is for the jury to read at
home, at their own pace: what PULSAR is, how we built it, what it measures and what it does not, and every NASA
source with its link. The landing stays the default, so the live presentation cannot open the wrong edition.

## Done when
- With no parameter the page opens the landing: the same pitch screens in the same order as before, and no element
  of the extended edition (`[data-edition="extended"]`) is visible.
- `?edition=extended`, or the "Read at home" control on the landing, opens the extended edition, and the URL keeps the
  choice. A link back to the landing goes to the pitch with no parameter. Nothing in this edition is timed and nothing
  advances on its own.
- The extended edition is one scrollable page with these sections, each a `[data-section]` with a heading and text:
  `problem` (the challenge and why fatigue matters in spaceflight), `how-it-works` (vision measures, the classifier
  estimates, the rules engine decides, Gemma only phrases the verdict; everything local), `how-we-built-it` (three
  verticals, one contract, goals with an acceptance test before the code), `data-and-sources`, `limits` (not a medical
  device, no SANS detection, no camera-based HRV, a NASA source does not mean NASA validated the model), `numbers`,
  `run-it` (how to start it locally, the repository link and, if there is a hosted copy, what that copy sends to the
  server) and `team`.
- `data-and-sources` lists every source in `shared/sources.json` whose URL is on a `nasa.gov` domain, each as a link to
  that exact URL and labelled with its id. Every other external link in the extended edition is also a URL from
  `shared/sources.json`, the repository (`github.com/alexvinola/nasa-hackathon`) or Google Fonts.
- Each figure in `numbers` is an element with `data-evidence="<repo path>"`, and that path exists in the repository
  (e.g. `backend/bench/voice_latency.json`). There are none without it: no figure is quoted that was not measured.
- EN / ES switches every section heading in the extended edition, and no section is empty in either language.
- With the network blocked the extended edition renders all its sections (external links are links, never fetched),
  and at 390 px wide the page has no horizontal scroll.

## Check
`make check-G12` → `frontend/e2e/acceptance/g12-extended-pitch.spec.ts` (Playwright, opening
`docs/brand/pulsar-intro.html` as a file with the network blocked; it reads `shared/sources.json` to check the links).

## Out of scope
A separate site or a page in the Next.js app, hosting the page, new sources (they go into `shared/sources.json`
first), changing the timing or the script of the landing, rewriting the Q&A dialog (it can stay or link to the extended
edition).
