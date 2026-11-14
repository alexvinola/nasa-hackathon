# G10 · Crewmate emergency (optional)

Owner: FS2 · Branch: `goal/G10-crew-emergency` · Depends on: G4, G5 · Optional: yes

## Goal
The challenge video's scenario (`challenge-video`): halfway to Mars a crewmate has a sharp chest pain and collapses.
A short yes/no checklist walks a non-doctor through the first steps and always ends in calling the flight surgeon.
The rules engine picks every step from a file; Gemma may only read a step aloud, never write or choose one.

## Done when
- The protocol the steps follow is registered in `shared/sources.json` (an official first-aid or resuscitation
  guideline) before any step is written, and every step and question carries a `source` that exists there.
- `backend/assets/emergency.json` holds the yes/no tree. `POST /emergency/next` with the answers so far returns the
  next question or step, the `escalation` and the `source`; the same answers always return the same response.
- Every path through the tree reaches `escalation: FLIGHT_SURGEON` (the test enumerates all of them); "chest pain"
  or "not responding" returns `FLIGHT_SURGEON` from its first step.
- The endpoint answers with Ollama stopped: no LLM call on this path.
- The HUD has a one-click "Crewmate emergency" entry that shows "Not a medical device".

## Check
`make check-G10` → `backend/tests/acceptance/test_emergency.py` (pytest).

## Out of scope
Saying what the crewmate has ("heart attack"), drug names or doses, steps beyond the registered guideline, measuring
the crewmate with the camera, ECG.
