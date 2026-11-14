"""Inspiration4 clinical labs (OSDR OSD-569 and OSD-575): what changes the day after landing.

uv run --with pandas python research/nasa-data/labs.py > research/nasa-data/findings/labs.txt

Four crew (C001-C004), seven draws: L-92, L-44, L-3 days before launch, R+1, R+45, R+82, R+194 days after
return. A change counts as a pattern only if all four crew move the same way at R+1 against three different
preflight baselines; anything weaker is reported as fragile. Descriptive only: n = 4, no statistics.
"""

import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent / "raw"
PANELS = {"cbc": "Complete blood count", "cmp": "Comprehensive metabolic panel", "cardio": "Serum cardiovascular panel"}
BASELINES = {"all preflight": ["L-92", "L-44", "L-3"], "without L-44": ["L-92", "L-3"], "L-3 only": ["L-3"]}
AFTER = ["R+1", "R+45", "R+82", "R+194"]


def load(panel):
    df = pd.read_csv(RAW / f"{panel}.csv", encoding="utf-8-sig")
    sample = df.columns[0]
    df["crew"] = df[sample].str.extract(r"^(C\d+)")
    df["time"] = df[sample].str.extract(r"_(L-\d+|R\+\d+)")
    return df


def measures(df):
    return [c for c in df.columns if "_value_" in c or "_concentration_" in c]


def label(column):
    return column.replace("_value", "").replace("_concentration", "")


def change(df, column, baseline, at):
    values = df.assign(v=pd.to_numeric(df[column], errors="coerce"))
    base = values[values.time.isin(baseline)].groupby("crew").v.mean()
    later = values[values.time == at].set_index("crew").v
    return ((later - base) / base * 100).dropna()


def consistent(pct):
    return len(pct) == 4 and (all(pct > 0) or all(pct < 0))


def report(panel, title):
    df = load(panel)
    print(f"\n## {title} ({df.crew.nunique()} crew x {df.time.nunique()} draws)\n")

    ranges = [(label(c), c.replace("_value_", "_range_min_"), c.replace("_value_", "_range_max_")) for c in measures(df)]
    ranges = [r for r in ranges if r[1] in df and r[2] in df]
    if ranges:
        print("Lab reference ranges (from the dataset):")
        for name, lo, hi in ranges:
            print(f"  {name:<58} {sorted(set(df[lo].dropna()))} - {sorted(set(df[hi].dropna()))}")
        print("\nValues outside the reference range (crew count low/high per draw):")
        for name, lo, hi in ranges:
            col = next(c for c in measures(df) if label(c) == name)
            v = pd.to_numeric(df[col], errors="coerce")
            low, high = v < pd.to_numeric(df[lo], errors="coerce"), v > pd.to_numeric(df[hi], errors="coerce")
            for t in [*BASELINES["all preflight"], *AFTER]:
                m = df.time == t
                if (low & m).sum() or (high & m).sum():
                    print(f"  {name:<58} {t:<6} low={int((low & m).sum())} high={int((high & m).sum())}")

    print("\nDay after landing (R+1) vs preflight, all 4 crew in the same direction:")
    for col in measures(df):
        verdicts = {name: change(df, col, base, "R+1") for name, base in BASELINES.items()}
        hits = {name: consistent(p) for name, p in verdicts.items()}
        if not any(hits.values()):
            continue
        verdict = "ROBUST " if all(hits.values()) else "fragile"
        detail = "  ".join(f"{n}: {'4/4' if hits[n] else '-'} {p.mean():+.0f}%" for n, p in verdicts.items())
        print(f"  {verdict} {label(col):<58} {detail}")
        if verdict.startswith("ROBUST"):
            trend = "  ".join(f"{t} {change(df, col, BASELINES['without L-44'], t).mean():+.0f}%" for t in AFTER)
            print(f"          {'':<58} later vs preflight without L-44: {trend}")


if __name__ == "__main__":
    missing = [p for p in PANELS if not (RAW / f"{p}.csv").exists()]
    if missing:
        sys.exit(f"missing raw files {missing}: run research/nasa-data/fetch.sh")
    print(__doc__.strip())
    for panel, title in PANELS.items():
        report(panel, title)
