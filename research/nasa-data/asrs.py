"""NASA ASRS fatigue report sets (100 de-identified aviation incident reports): what fatigue incidents look like.

uv run --with pypdf python research/nasa-data/asrs.py > research/nasa-data/findings/asrs.txt

Counts structured fields and narrative keywords. ASRS reports are voluntary and not corroborated: counts
describe these 100 reports, not how often anything happens.
"""

import re
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

RAW = Path(__file__).resolve().parent / "raw"
SETS = ["asrs_air_carrier_fatigue.pdf", "asrs_commuter_corporate_fatigue.pdf"]

def reports(text):
    body = text[text.find("Report Synopses"):]
    starts = [m.start() for m in re.finditer(r"ACN: \d+ \(\d+ of \d+\)\s*\nTime / Day", body)]
    return [body[a:b] for a, b in zip(starts, starts[1:] + [len(body)])]

def field(rep, name):
    return [v.strip() for v in re.findall(rf"^{re.escape(name)}\s*:\s*(.+)$", rep, re.M)]

counts = {k: Counter() for k in ("time", "phase", "human", "anomaly", "primary", "result")}
total, approach, narratives = 0, 0, []
for name in SETS:
    if not (RAW / name).exists():
        sys.exit(f"missing raw/{name}: run research/nasa-data/fetch.sh")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(RAW / name).pages)
    for rep in reports(text):
        total += 1
        counts["time"].update(set(field(rep, "Local Time Of Day")))
        counts["phase"].update(set(field(rep, "Flight Phase")))
        approach += bool(set(field(rep, "Flight Phase")) & {"Initial Approach", "Final Approach", "Descent", "Landing"})
        counts["human"].update(set(field(rep, "Human Factors")))
        counts["anomaly"].update({a.split(":")[0].strip() for a in re.findall(r"^Anomaly\.(.+)$", rep, re.M)})
        counts["primary"].update(set(field(rep, "Primary Problem")))
        counts["result"].update(set(field(rep, "Result.Flight Crew")))
        n = rep.split("Narrative: 1", 1)[-1].lower()
        narratives.append(n)
print(__doc__.strip())
print("\nreports parsed:", total)
for k, c in counts.items():
    print(f"\n-- {k}"); [print(f"   {n:>3}  {v}") for v, n in c.most_common(9)]
words = {"slept / sleep": r"\bslep|\bsleep", "reserve / schedule": r"\breserve|\bschedul", "red-eye / night / overnight": r"red.?eye|overnight|\bnight\b",
         "duty / hours awake": r"\bduty\b|hours awake|awake for", "circadian / WOCL": r"circadian|wocl|window of circadian", "nap / rest": r"\bnap|\brest\b",
         "microsleep / fell asleep / nodded": r"micro.?sleep|fell asleep|nodded|dozed"}
print(f"\n-- reports in approach, descent or landing: {approach} of {total}")
print("\n-- narratives mentioning (of", total, ")")
for label, rx in words.items():
    print(f"   {sum(bool(re.search(rx, n)) for n in narratives):>3}  {label}")
