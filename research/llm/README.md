# Gemma 4 E4B probe

Measured on 2026-11-14 on Alex's laptop (Apple M5, 16 GB RAM), Ollama 0.40.16, `gemma4:e4b-it-qat`, `think: false`,
temperature 0. Script: `gemma_probe.py`. One run each: indicative, not a benchmark; G5's bench is the number to quote.

| Check | Result | Time |
|---|---|---|
| Cold load | 6.1 GB download; 3.1 GB loaded, 100% GPU, 4K context | 4.6 s once |
| Verdict to speech, RED (`shared/examples/red-emergency.json`) | 2 sentences, says flight surgeon | 1.3 s |
| Verdict to speech, AMBER (scenario 02) | 2 sentences | 0.9 s |
| Photo of a blood-pressure monitor to JSON (structured output) | `{"systolic": 138, "diastolic": 91, "pulse": 77}`: exact | 1.2 s |
| Describe an image (PULSAR mascot) | Correct one-sentence description | 2.6 s |
| Speech to text (16 kHz WAV from macOS `say`, sent in the message's `images` field) | Exact transcript | 1.1 s |

Generation speed: about 39 tokens/s.

## What it means for PULSAR

- **One model for voice in and out.** Gemma 4 E4B transcribes audio itself, so faster-whisper may not be needed.
  Only tested on clean synthetic speech: test a real microphone in the venue before dropping whisper. In Ollama
  0.40.16 the audio goes in the `images` field; an `audio` field is silently ignored ("The audio is silent").
- **Keep two calls.** Transcribe first, send the text to the rules engine, then phrase the verdict. Never let the
  model answer the spoken question directly: the rules engine decides.
- **Vision for self-report.** A photo of a BP monitor, glucometer or thermometer can fill `selfReport` with structured
  output; the astronaut confirms the numbers before they count.
- **The prompt needs work (G5).** The RED answer said "multiple critical alerts" instead of naming what was detected,
  and the AMBER answer read the countermeasure id aloud ("CM-SLEEP-01"). Pass the factor messages and the
  countermeasure's first step as text, never ids.
- Disable thinking (`think: false`): it is on by default and only adds latency for two sentences.

## Can Gemma verify the camera? Eye state on labelled MRL Eye crops

`eye_state_probe.py`, 2026-11-14, same laptop and model, temperature 0, `pulsar.vision.verify.look` (the prompt
`POST /vision/verify` uses). MRL images are small infrared crops of one eye, upscaled to 224 px.

| Truth | Gemma said open | closed | unclear |
|---|---|---|---|
| Open (25) | 24 | 0 | 1 |
| Closed (25) | 15 | 2 | 8 |

A prompt written for a single-eye infrared crop did not change it: closed eyes recognised 3 of 15, open 15 of 15.

**Gemma 4 E4B almost never confirms a closed eye on these crops**: when it says "closed" it is right, but it misses
most closed eyes. On a full-colour webcam face it may do better; the HUD shows the live agreement rate so that is
measured, not assumed. Until then the AI check is evidence beside the reading, never a reason to trust or
discard PERCLOS, and a disagreement on "closed" is expected more often from Gemma's side than from MediaPipe's.
