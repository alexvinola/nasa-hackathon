# PULSAR: Personal Unit for Learning, Support, Assistance & Reminders

*Your personal health companion in space.*

![Meet P.U.L.S.A.R., the mascot and tagline](shots/live-02-intro.png)

## What PULSAR Does

PULSAR is an offline health companion for astronauts on long missions. It runs on the device, with no network and no cloud calls, so no crew health data leaves the spacecraft. It watches the astronaut's fatigue through the camera, tracks vital signs and cabin conditions, and guides the crew through measurements, relaxation and alerts, by voice, text or on-screen controls.

![Main screen: live camera with the face mesh, fatigue readings and the assistant](shots/live-01-main-hud.png)

*Main screen. Fatigue, eye closure (PERCLOS) and yawns are measured live from the camera, drawn as a face mesh. In this demo the pulse, sleep, mood and cabin readings are simulated, and the screen says so.*

## How It Works

**1. Vision measures, nothing else.** A camera worker in the browser extracts eye closure, blink and yawn signals with MediaPipe. The fatigue classifier only estimates a fatigue score from those signals.

**2. A rules engine decides.** Eight rules turn fatigue, eye-closure, sleep, reaction time, mood, cabin CO2 and radiation readings into GREEN, AMBER or RED. Each rule states either its source or that its limit is a team assumption, and several limits are still placeholders to be calibrated. Heart rate, blood pressure, blood glucose and body temperature have no rule yet: PULSAR shows them and says they are not judged. The language model never decides a status, an escalation or a health judgement.

**3. Voice and text, through a closed list of actions.** The astronaut can speak or type, for example "log my blood pressure", "I drank three glasses of water", "how am I doing?" or "I'm stressed, help me relax". Speech recognition and the voice both run locally. The language model only chooses one action from a fixed catalogue and phrases two short sentences from the verdict. It cannot write an action, a number or a status on its own, and every number it passes on is checked against the bounds of the contract.

**4. A body twin that teaches the measurement.** A 3D body shows where each indicator sits. Selecting a marker opens a step-by-step guide with an animation that highlights each step.

**5. Habits, relaxation and a reaction test.** Four habits with a score and a streak, three guided relaxation exercises, and a short reaction test that can stop an alarm.

## Fill In Measurements With a Sentence

The astronaut does not have to type into a form. Saying or typing a sentence saves the value directly, and the measurement form shows it as logged. Every number is checked against the bounds of the contract before it is saved.

In the screenshots the astronaut said *"Today I had 8,5 hours of sleep"*. PULSAR answered "Logged: sleep 8.5", and the form shows "1 of 6 logged" with sleep at 8.5 h, in range, and the rules engine's verdict as GREEN.

A single sentence can also fill every measurement at once:

> *pulse 72, blood pressure 120 80, glucose 95, temperature 36.8, sleep 7, mood 4*

![Voice sentence logged as a measurement; the form shows it in range](shots/live-11-measurement-form.png)

## Symptoms

Describing a symptom opens the information panel for the matching body zone, with what to do, possible problems and the NASA risk it relates to. PULSAR does not diagnose; it explains and points to the flight surgeon. Examples: "my head hurts" opens the head panel, "I have a pain in my back" opens the spine panel, and "I want to see my symptoms" opens the symptoms tab. PULSAR understands Spanish and English.

![Head and balance information panel, opened while the sleep sentence was logged](shots/live-10-symptom-head-voice-log.png)

## Alerts

Three levels exist: green (safe), amber (tell the crew) and red (flight surgeon, act now). Each alert shows what to do, in order, and is stopped by acknowledging it or by passing the reaction test. The three screenshots below were triggered with the demo simulation over the live camera view, so the readings in them are simulated.

| Rule | Level | Limit in the demo |
| --- | --- | --- |
| Fatigue score high | Red | 0.70 (team placeholder) |
| Eye closure (PERCLOS) high | Amber | 11% of the time, from a public drowsiness dataset |
| Sleep under 6 hours | Amber | 6 h |
| Slow reaction time (PVT) | Amber | 320 ms mean (placeholder) |
| Low mood | Amber | 2 or less on a 1-5 scale (team assumption) |
| Cabin CO2 high | Amber | 4.0 mmHg (placeholder) |
| Radiation dose high | Red | 5 mSv (demo placeholder, simulated dose) |
| Arm asymmetry | Red | 0.35 (placeholder, secondary camera signal) |

![Red alert: not safe to stay awake](shots/live-04-alert-danger-fatigue.png)
![Red alert: high radiation](shots/live-05-alert-radiation.png)
![Amber alert: high cabin CO2](shots/live-06-alert-co2.png)

### Reaction Test

A fatigue alarm stops when the astronaut passes a short reaction test: three stimuli, each counted if the answer takes between 100 and 355 ms. Faster than 100 ms is a guess, 355 ms or slower is a lapse (the PVT-B criterion), and pressing too early or not responding within 2 seconds is a miss. All three must pass.

![Reaction self test](shots/live-03-reaction-test.png)

## Habit Journal

Four daily habits (sleep, exercise, hydration and relaxation) feed a daily score, a level and a streak, with 3-, 7- and 30-day views in the side panel. The expanded history shows the average score, good days, best streak, a per-habit strip and the best and weakest weekday, for 7, 30 or 60 days. The history in the demo is generated sample data, not real measurements, and the habit targets are team assumptions.

![Habits panel next to the live camera](shots/live-09-habits-panel-camera.png)
![Habit journal: 30-day history](shots/live-08-habits-history.png)

## Relaxation

Three guided exercises: slow breathing (5 cycles), eye rest (40 seconds) and release tension (80 seconds). They are general guidance, not a treatment, and the screen says so.

![Relaxation menu](shots/live-07-relaxation.png)

## How It Addresses the Challenge

The challenge asks for health monitoring software that helps astronauts spot changes in their own health on long missions, without relying on the ground. PULSAR covers that loop on one device: it measures, decides with transparent rules, explains the result in plain language and shows the next step. Every limit is traceable, so the crew and the medical officer can see why PULSAR says what it says.

## Why It Matters

On a mission to deep space, a message to the ground can take minutes, and a crew cannot always wait for a doctor. A tool that works offline, explains itself and is simple enough to use under fatigue gives the crew an early, understandable second opinion. The aim is to help them notice a change sooner, not to replace clinical care.

## Scope and Limits

PULSAR is a decision-support prototype, not a medical device. In the demo the camera is real and measures fatigue, eye closure and yawns, while pulse, sleep, mood and cabin readings are simulated, and the alert screenshots use simulated values. PULSAR does not diagnose, does not detect SANS, and does not measure heart-rate variability through the camera. It reports what the rules engine decides from the readings it has, and it does not judge the values that have no rule yet.
