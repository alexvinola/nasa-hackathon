"""Gemma 4 probe for PULSAR through Ollama: verdict phrasing (G5) and image reading. Results: README.md.

uv run --with pillow python research/llm/bp_image.py /tmp/bp.png
python3 research/llm/gemma_probe.py gemma4:e4b-it-qat . /tmp/bp.png docs/brand/pulsar-mascot.webp
"""
import base64, json, sys, time, urllib.request

MODEL, REPO, BP, OTHER = sys.argv[1:5]
SYSTEM = """You are PULSAR, the onboard health assistant of a long-duration space mission.
The astronaut is not a doctor and may be in hands-free mode.
Your only task is to turn the rules engine's verdict into spoken guidance.
RULES:
1. Answer in 2 short sentences at most; they will be read aloud.
2. Use only the data in [VERDICT] and [ENVIRONMENT]. Do not add diagnoses, figures or causes that are not there.
3. First sentence: what was detected. Second sentence: the immediate action or the next voice command.
4. If [VERDICT].escalation is FLIGHT_SURGEON, say so explicitly."""


def chat(messages, fmt=None):
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False, "options": {"temperature": 0}}
    if fmt: body["format"] = fmt
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.monotonic(); out = json.load(urllib.request.urlopen(req, timeout=600)); wall = time.monotonic() - t
    tok_s = out.get("eval_count", 0) / (out.get("eval_duration", 1) / 1e9)
    return out["message"]["content"].strip(), wall, out.get("load_duration", 0) / 1e9, tok_s


def image(path):
    return base64.b64encode(open(path, "rb").read()).decode()


red = json.load(open(f"{REPO}/shared/examples/red-emergency.json"))
tired = json.load(open(f"{REPO}/shared/scenarios/02-short-sleep.json"))
verdict_tired = {"status": "AMBER", "escalation": "CREW", "hrpRisk": "SLEEP_AND_SCHEDULES", "affectedSystems": ["NERVOUS"],
                 "factors": [{"signal": "selfReport.sleepHoursLast24h", "value": 5.0, "threshold": 6, "message": "Under 6 hours of sleep: slower reactions expected"},
                             {"signal": "biometrics.lastPvtMeanMs", "value": 345, "threshold": 320, "message": "Reaction test slower than baseline"}],
                 "countermeasureId": "CM-SLEEP-01"}

cases = [("warm-up (load)", [{"role": "user", "content": "Say OK."}], None)]
for name, decision, env in (("verdict RED", red["decision"], red["environment"]), ("verdict AMBER", verdict_tired, tired["input"]["environment"])):
    cases.append((name, [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": f"[VERDICT]\n{json.dumps(decision)}\n[ENVIRONMENT]\n{json.dumps(env)}"}], None))
bp_schema = {"type": "object", "properties": {"systolic": {"type": "integer"}, "diastolic": {"type": "integer"}, "pulse": {"type": "integer"}},
             "required": ["systolic", "diastolic", "pulse"]}
cases.append(("image: BP monitor -> JSON", [{"role": "user", "content": "Read this blood pressure monitor display. Return the numbers exactly as shown.", "images": [image(BP)]}], bp_schema))
cases.append(("image: describe", [{"role": "user", "content": "Describe this image in one sentence.", "images": [image(OTHER)]}], None))

for name, messages, fmt in cases:
    text, wall, load, tok_s = chat(messages, fmt)
    print(f"--- {name}: {wall:.1f} s total, load {load:.1f} s, {tok_s:.0f} tok/s\n{text}\n")
