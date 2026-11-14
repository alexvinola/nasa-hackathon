"""Render ``out/fatigue_report.md`` from the measured numbers. No number is written by hand here.

The report is built around what the run demonstrates: the evidence each feature gives on its own, the
shipped model out of fold, and the comparison with the browser's current formula with intervals over
subjects. Sentences that depend on a result ("the interval includes 0") are generated from the numbers,
so the wording cannot drift from them. The three alternative configurations, the fold-internal selection
and the calibration sensitivity come afterwards, labelled as secondary analyses.
"""

from __future__ import annotations

from statistics import median

from . import fatigue_features as ff

STATES = list(ff.CLASS_NAMES)
STATE_TITLE = {"alert": "alert", "low_vigilance": "low vigilance", "drowsy": "drowsy"}
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "last"}


def num(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def pct(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{100 * value:.{digits}f} %"


def interval(pair, digits: int = 3) -> str:
    return "n/a" if not pair else f"{pair[0]:.{digits}f} to {pair[1]:.{digits}f}"


def pct_interval(pair, digits: int = 1) -> str:
    return "n/a" if not pair else f"{100 * pair[0]:.{digits}f} to {100 * pair[1]:.{digits}f} %"


def excludes(pair, value: float = 0.0) -> bool:
    """True when a 95 % interval lies entirely on one side of ``value``."""
    return bool(pair) and (pair[0] > value or pair[1] < value)


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def confusion(matrix: list[list[int]]) -> str:
    header = ["true \\ predicted"] + [STATE_TITLE[s] for s in STATES] + ["recall"]
    rows = []
    for k, state in enumerate(STATES):
        total = sum(matrix[k])
        rows.append([STATE_TITLE[state]] + [str(c) for c in matrix[k]] + [pct(matrix[k][k] / total if total else None)])
    return table(header, rows)


def signed(value, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}"


def pvt_summary(metrics: dict) -> str:
    """The PVT line of "In short"."""
    dz = metrics.get("drozy_validation")
    if not dz:
        return f"- **PVT.** Not measured: {metrics['pvt_correlation_note']}\n"
    h = dz["headline"]
    recording = dz["results"]["per_recording"]
    within = dz["results"]["within_subject"]
    pvt = "pvt_mean_rt_ms"

    def per_test(signal: str) -> str:
        c = recording[signal][pvt]
        return f"{signed(c['spearman'])} (Pearson {signed(c['r'])})"

    w = within["fatigue_score"][pvt]["r"]
    return (
        f"- **PVT, on people the model never saw (DROZY, {CITATION_SHORT}).** `pvt_correlation` = **{signed(h['value'])}**: Spearman correlation, one point per "
        f"test ({h['n_recordings']} tests of {dz['dataset']['subjects_scored']} people), between the mean `fatigueScore` and the mean PVT reaction time "
        f"(Pearson {signed(h['pearson_r'])}). PERCLOS alone: {per_test('perclos')}; the former formula: {per_test('browser_formula')}. "
        f"Within each person, window by window, the score's correlation with reaction time has median {signed(w['median'])} "
        f"({signed(w['min'])} to {signed(w['max'])}), positive in {w['positive']} of {w['subjects']} people. Near-infrared video and no interval: see the DROZY section.\n"
    )


CITATION_SHORT = "Massoz et al. 2016, WACV"
SIGNAL_TITLE = {"fatigue_score": "model `fatigueScore`", "perclos": "PERCLOS alone", "browser_formula": "former browser formula"}


def drozy_section(dz: dict, rldd_score: dict) -> list[str]:
    """The DROZY validation: every number from ``drozy_validation``; KSS figures carry the note that KSS is not registered."""
    out: list[str] = []
    add = out.append
    data = dz["dataset"]
    results = dz["results"]
    h = dz["headline"]
    pvt, kss = "pvt_mean_rt_ms", "kss"
    signals = list(dz["signals"])
    add("## Reaction time and sleepiness on DROZY (held out)\n")
    add(f"DROZY: {dz['citation']} (source `{dz['source']}`). {dz['what']} {dz['licence']}\n")
    faces = data["face_found"]
    fps = data["processed_fps"]
    add(
        f"- **Data.** {data['tests_scored']} tests of {data['subjects_scored']} people, about 10 minutes each ({data['tests_found']} found, "
        f"{len(data['tests_failed'])} failed). Frame times: {data['frame_times']}; processed rate {num(fps.get('min'), 1)} to {num(fps.get('max'), 1)} "
        f"per second (median {num(fps.get('median'), 1)}). Face found in {pct(faces['overall'], 2)} of the frames, lowest test {pct(faces['min_per_test'], 2)}.\n"
        f"- **Windows.** {data['window_rule']} {data['windows']} windows, {data['windows_rejected']} rejected, {data['windows_scored']} scored "
        f"({data['windows_scored_without_stimulus']} of them without a PVT stimulus, left out of the window-level PVT figures).\n"
        f"- **Targets.** Reaction time: {dz['targets'][pvt]}. {dz['targets'][kss]}\n"
        f"- **Headline.** `pvt_correlation` = {signed(h['value'])} (n = {h['n_recordings']} tests). {h['why']}\n"
    )
    rows = []
    for signal in signals:
        p, k = results["per_recording"][signal][pvt], results["per_recording"][signal][kss]
        rows.append([SIGNAL_TITLE.get(signal, signal), f"{signed(p['r'])} / {signed(p['spearman'])}", p["n"], f"{signed(k['r'])} / {signed(k['spearman'])}", k["n"]])
    add("**One point per test** (mean of the signal over the test's scored windows):\n")
    add(table(["signal", "vs mean PVT reaction time, Pearson / Spearman", "tests", "vs KSS, Pearson / Spearman *", "tests"], rows) + "\n")

    def spread(block: dict) -> str:
        return f"{signed(block['median'])} ({signed(block['min'])} to {signed(block['max'])})"

    rows = []
    for signal in signals:
        w = results["within_subject"][signal]
        rows.append(
            [
                SIGNAL_TITLE.get(signal, signal),
                spread(w[pvt]["r"]),
                f"{w[pvt]['r']['positive']} of {w[pvt]['r']['subjects']}",
                spread(w[kss]["r"]),
                f"{w[kss]['r']['positive']} of {w[kss]['r']['subjects']}",
            ]
        )
    add(
        "**Within each person** (Pearson r over that person's windows; median across people, lowest to highest, and in how many it is positive). "
        "A person's own level is a constant here, so differences between people cannot drive it:\n"
    )
    add(table(["signal", "vs PVT reaction time of the window", "people positive", "vs KSS *", "people positive"], rows) + "\n")
    rows = []
    for signal in signals:
        p, k = results["pooled_windows"][signal][pvt], results["pooled_windows"][signal][kss]
        rows.append([SIGNAL_TITLE.get(signal, signal), f"{signed(p['r'])} / {signed(p['spearman'])}", p["n"], f"{signed(k['r'])} / {signed(k['spearman'])}", k["n"]])
    add("Every scored window pooled (overlapping windows: the counts are not sample sizes):\n")
    add(table(["signal", "vs PVT reaction time, Pearson / Spearman", "windows", "vs KSS, Pearson / Spearman *", "windows"], rows) + "\n")
    add(f"\\* {dz['targets'][kss]}\n")

    model_s = results["per_recording"]["fatigue_score"][pvt]["spearman"]
    lines = []
    for other in ("perclos", "browser_formula"):
        value = results["per_recording"][other][pvt]["spearman"]
        if model_s is not None and value is not None:
            lines.append(f"{'above' if model_s > value else 'below' if model_s < value else 'equal to'} that of {SIGNAL_TITLE[other].replace('former', 'the former')} ({signed(value)})")
    if lines:
        add(
            f"**Reading.** Per test against reaction time, the model's Spearman ({signed(model_s)}) is {' and '.join(lines)}. With 36 tests and no interval, "
            "these differences are not evidence that one signal is better than another. A positive sign means the signal rises as reactions slow down.\n"
        )
    d = dz["score_distribution"]["fatigue_score"]
    if d:
        add(
            f"The model's `fatigueScore` on DROZY windows runs from {num(d['min'], 2)} to {num(d['max'], 2)} (middle half {num(d['p25'], 2)} to "
            f"{num(d['p75'], 2)}); out of fold on RLDD it ran from {num(rldd_score['min'], 2)} to {num(rldd_score['max'], 2)}. A threshold on the score "
            "cannot be read off DROZY: its video is not the demo's.\n"
        )
    add("Limits of this validation:\n")
    add("\n".join(f"- {text}" for text in dz["limits"]) + "\n")
    rows = [
        [
            c["recording"],
            num(c["processed_fps"], 1),
            pct(c["face_found"], 2),
            num(c["longest_no_face_s"], 1),
            f"{c['windows'] - c['windows_rejected']} of {c['windows']}",
        ]
        for c in dz["recordings"]
    ]
    add("Every DROZY test (coverage only: no test's reaction times or KSS are listed, per the licence):\n")
    add(table(["test", "processed per second", "face found", "longest no-face (s)", "windows scored"], rows) + "\n")
    if data["tests_failed"]:
        add("Failed: " + "; ".join(f"{f['recording']}: {f['error']}" for f in data["tests_failed"]) + "\n")
    return out


SIGNAL_TITLE = {"perclos": "PERCLOS", "browser_formula": "browser formula", "model_fatigue_score": "model fatigueScore"}


def thresholds_section(th: dict) -> list[str]:
    """Where a threshold would sit on each camera signal and what it would cost: every number from ``thresholds``."""
    lines = ["## Where a threshold would sit\n"]
    lines.append(
        "The rules engine decides with thresholds on PERCLOS and on `fatigueScore`; both are team placeholders. This section does not "
        f"choose them: it shows what each cut costs. {th['how']}\n"
    )
    rows = []
    for name, points in th["signals"].items():
        for point in points:
            fold = point["out_of_fold"]
            alert, drowsy = fold["alert_per_subject"], fold["drowsy_per_subject"]
            rows.append([
                SIGNAL_TITLE.get(name, name),
                pct(point["false_alarm_rate"], 0),
                num(point["cut"]),
                " / ".join(pct(fold["windows"][state]) for state in STATES),
                f"{pct(alert['median'])} ({pct(alert['min'])} to {pct(alert['max'])})",
                f"{pct(drowsy['median'])} ({pct(drowsy['min'])} to {pct(drowsy['max'])}), {drowsy['subjects_with_any']} of {drowsy['subjects']}",
            ])
    lines.append(
        table(
            ["signal", "alert windows allowed to fire", "cut (fires above it)", "windows firing out of fold (alert / low / drowsy)",
             "per person, alert windows firing: median (range)", "per person, drowsy windows firing: median (range), people with any"],
            rows,
        )
        + "\n"
    )
    if th["engine_rules"]:
        lines.append("**The thresholds the engine applies today**, on the same windows:\n")
        rows = []
        for entry in th["engine_rules"].values():
            rule, drowsy = entry["rule"], entry["drowsy_per_subject"]
            rows.append([
                f"`{rule['id']}` ({rule['status']})",
                SIGNAL_TITLE.get(entry["signal"], entry["signal"]),
                f"{rule['operator']} {num(rule['threshold'], 2)}",
                str(entry["windows_firing"]),
                " / ".join(pct(entry["windows"][state]) for state in STATES),
                f"{drowsy['subjects_with_any']} of {drowsy['subjects']}",
            ])
        lines.append(
            table(["rule", "compared with", "fires when", "windows firing", "share firing (alert / low / drowsy)", "people whose drowsy video fires at all"], rows)
            + "\n"
        )
    lines.append("\n".join(f"- {text}" for text in th["limits"]) + "\n")
    return lines


def render(metrics: dict, model: dict) -> str:
    chosen = metrics["chosen"]
    name = chosen["configuration"]
    data = metrics["dataset"]
    windows = data["windows"]
    baseline = metrics["baseline"]
    ci = chosen["ci95_subject_bootstrap"]
    configurations = metrics["configurations"]
    nested = metrics["nested_selection"]
    sens = metrics["calibration_sensitivity"]
    video = metrics["video_level"]
    subjects = metrics["per_subject"]
    extraction = metrics["extraction"]
    evidence = metrics["feature_evidence"]
    stats = metrics["feature_statistics"][name]
    constants = metrics["features"]["constants"]
    score = chosen["score"]
    b_score = baseline["score"]
    b_model = baseline["as_three_class_model"]
    people = data["subjects_used"]
    limit = metrics.get("limit")
    needs_calibration = model["calibration"]["required"]
    parts: list[str] = []
    add = parts.append

    gap_binary = score["auc_alert_vs_drowsy"] - b_score["auc_alert_vs_drowsy"]
    gap_binary_ci = ci.get("score_minus_baseline_auc_alert_vs_drowsy")
    gap_three = metrics["auc"] - b_model["auc"]
    gap_three_ci = ci.get("auc_minus_baseline_as_model_auc")
    # Features whose own alert-vs-drowsy AUC is clearly above 0.5 on these subjects, and the ones that are not.
    carrying = [f for f in metrics["features"]["names"] if evidence[f]["ci95_subject_bootstrap"] and evidence[f]["ci95_subject_bootstrap"][0] > 0.5]
    silent = [f for f in metrics["features"]["names"] if f not in carrying]

    def feature_line(feature: str) -> str:
        e = evidence[feature]
        higher = e["subjects_higher_in_drowsy_video"]
        return (
            f"`{feature}` alone separates alert from drowsy windows with AUC {num(e['auc_alert_vs_drowsy'])} "
            f"({interval(e['ci95_subject_bootstrap'])}); it is higher in the drowsy video than in the alert one for "
            f"{higher['subjects']} of {higher['of']} people"
        )

    add("# Fatigue model on UTA-RLDD: what is demonstrated\n")
    if limit:
        add(f"> **Smoke run on the first {limit} subjects.** These numbers are not the result; run `make model` without `--limit`.\n")
    add(
        "Generated by `make model` (`data/pipeline.py`). Every number below is read from `data/out/metrics.json`; "
        "nothing is typed by hand, and the sentences that depend on a result are generated from it. It is not a medical device: "
        "the model estimates signs consistent with drowsiness, and the rules engine decides.\n"
    )

    # ------------------------------------------------------------------ summary
    add("## In short\n")
    add(
        f"- **Data.** {data['videos']} videos of {people} people ({num(data['hours_of_video'], 1)} h), three per person: "
        f"alert, low vigilance, drowsy, as rated by the person. {windows['evaluated']} windows of 60 s (one every 10 s) are scored.\n"
        f"- **Validation.** {metrics['validation']['scheme']}: every person is scored by a model that never saw them. "
        "All intervals are 95 % and resample people, not windows.\n"
        f"- **What ships.** Eye closure `{chosen['eye_method']}`, features `{chosen['normalisation']}`: "
        + ("what the browser worker already computes, with no calibration step. " if not needs_calibration else "with a calibration step. ")
        + "It is a fixed setting decided by the team, not the winner of a comparison (see \"The decision\").\n"
        f"- **Demonstrated, feature by feature.** {feature_line('perclos')}. {feature_line('mean_blink_duration_s')}.\n"
        f"- **The model.** Three states: AUC **{num(metrics['auc'])}** ({interval(ci.get('auc'))}), macro F1 **{num(metrics['macro_f1'])}** "
        f"({interval(ci.get('macro_f1'))}), accuracy {pct(chosen['accuracy'])} where chance is 33 %. Alert against drowsy, the `fatigueScore` "
        f"reaches AUC **{num(score['auc_alert_vs_drowsy'])}** ({interval(ci.get('score_auc_alert_vs_drowsy'))}).\n"
        f"- **Against the browser's current formula.** On the same windows the formula gets {num(b_score['auc_alert_vs_drowsy'])} "
        f"({interval(ci.get('baseline_auc_alert_vs_drowsy'))}) alert against drowsy. Difference {gap_binary:+.3f} ({interval(gap_binary_ci)}): "
        + ("the interval excludes 0." if excludes(gap_binary_ci) else f"the interval includes 0, so these {people} people do not show that the model beats the formula.")
        + f" On three states the difference in AUC is {gap_three:+.3f} ({interval(gap_three_ci)}), "
        + ("which excludes 0.\n" if excludes(gap_three_ci) else "which includes 0 too.\n")
        + f"- **Calibration.** A per-person eye threshold (EAR) depends on where its calibration comes from: taken from the person's alert video "
        f"it scores {num(sens['threshold_from_alert_video']['score_auc_alert_vs_drowsy'])} alert against drowsy, taken from the scored video "
        f"{num(sens['threshold_from_scored_video']['score_auc_alert_vs_drowsy'])}; `blendshape` without calibration scores "
        f"{num(sens['blendshape_absolute_same_windows']['score_auc_alert_vs_drowsy'])} on the same windows. Features calibrated per person go from "
        f"{num(sens['calibrated_features']['reference_from_alert_video']['score_auc_alert_vs_drowsy'])} to "
        f"{num(sens['calibrated_features']['reference_from_scored_video']['score_auc_alert_vs_drowsy'])} the same way.\n"
        + pvt_summary(metrics)
    )

    # ------------------------------------------------------------------ pitch
    add("## What can be said\n")
    features_hold = all(evidence[f]["ci95_subject_bootstrap"] and evidence[f]["ci95_subject_bootstrap"][0] > 0.5 for f in ("perclos", "mean_blink_duration_s"))
    model_holds = bool(ci.get("score_auc_alert_vs_drowsy")) and ci["score_auc_alert_vs_drowsy"][0] > 0.5
    may: list[str] = []
    may_not: list[str] = []
    if features_hold and model_holds:
        may.append(
            f"\"Eye closure and blink duration predict drowsiness on {people} people the model never saw.\" Behind it: PERCLOS alone AUC "
            f"{num(evidence['perclos']['auc_alert_vs_drowsy'])} ({interval(evidence['perclos']['ci95_subject_bootstrap'])}), blink duration alone "
            f"{num(evidence['mean_blink_duration_s']['auc_alert_vs_drowsy'])} ({interval(evidence['mean_blink_duration_s']['ci95_subject_bootstrap'])}), "
            f"the model {num(score['auc_alert_vs_drowsy'])} ({interval(ci.get('score_auc_alert_vs_drowsy'))}), alert against drowsy; every interval is above 0.5."
        )
    else:
        may_not.append(
            f"\"Eye closure and blink duration predict drowsiness on {people} people the model never saw\": not supported by this run, "
            "an interval reaches 0.5 (see the feature table and the model's interval)."
        )
    may.append("\"The camera estimates signs consistent with drowsiness; the rules engine decides.\"")
    may.append("\"Trained on volunteer drowsiness video with self-reported labels, not on astronauts.\"")
    may.append("Any number of `data/out/metrics.json`, exactly as measured and with its interval.")
    if excludes(gap_binary_ci) and gap_binary > 0:
        may.append(f"\"The model separates alert from drowsy better than the previous formula\" (difference {gap_binary:+.3f}, {interval(gap_binary_ci)}).")
    else:
        may_not.append(
            f"That the model beats the previous formula at telling alert from drowsy: the difference is {gap_binary:+.3f} and its interval "
            f"({interval(gap_binary_ci)}) includes 0."
        )
    if excludes(gap_three_ci) and gap_three > 0:
        may.append(
            f"\"It tells the three states apart better than the previous formula's single number\" (3-state AUC difference {gap_three:+.3f}, "
            f"{interval(gap_three_ci)}), and only that."
        )
    else:
        may_not.append(f"That it tells the three states apart better than the previous formula: the difference is {gap_three:+.3f} ({interval(gap_three_ci)}).")
    if silent:
        may_not.append(
            "That " + ", ".join(f"`{f}`" for f in silent) + " add evidence: on their own their alert-vs-drowsy AUC is not distinguishable from 0.5 "
            "here. They stay in the model: features are not dropped after looking at results."
        )
    may_not.append("That a personal calibration or the EAR method makes it better: RLDD cannot show it (see \"What a rested calibration is worth\").")
    dz = metrics.get("drozy_validation")
    if dz:
        h = dz["headline"]
        if h["value"] is not None:
            may.append(
                f"\"On {dz['dataset']['subjects_scored']} people it never saw (DROZY, near-infrared video), the score's correlation with mean PVT reaction time "
                f"per test is {signed(h['value'])} (Spearman, {h['n_recordings']} tests).\" Always with that wording, its Pearson value ({signed(h['pearson_r'])}) and "
                "\"no interval was computed\"; cite Massoz et al. (2016), WACV."
            )
        may_not.append(
            "That the score equals alertness, performance or reaction time: the RLDD labels are the person's own rating, and on DROZY the score "
            "only correlates with reaction time (see \"Reaction time and sleepiness on DROZY\")."
        )
        may_not.append(
            "That the model tracks reaction time or sleepiness better (or worse) than PERCLOS alone or the former formula: DROZY gives one number "
            "per signal over 36 tests and no interval, so the three cannot be ranked."
        )
    else:
        may_not.append("That the score equals alertness, performance or reaction time: the labels are the person's own rating and no PVT was measured.")
    may_not.append("\"Detects fatigue\", \"microsleep\", a diagnosis, or anything about spaceflight: none of it was measured.")
    add("May be said:\n")
    add("\n".join(f"- {text}" for text in may) + "\n")
    add("May not be said:\n")
    add("\n".join(f"- {text}" for text in may_not) + "\n")

    # ------------------------------------------------------------------ decision
    add("## The decision\n")
    rank = chosen["rank_among_the_four_by_auc"]
    add(f"{chosen['how']}\n")
    add(
        f"What that means for the numbers: no step of `make model` chooses the configuration, so the headline carries no winner's optimism. "
        f"Among the four combinations that were measured, the shipped one ranks {ORDINAL.get(rank, str(rank))} on 3-state AUC "
        "(table under \"Secondary analyses\"). The decision was taken after seeing those analyses, so they are part of its history, not an independent confirmation.\n"
    )

    # ------------------------------------------------------------------ data
    add("## The data\n")
    fps = data["processed_fps"]
    no_face = data["no_face"]
    orientation = data["orientation"]
    add(
        f"UTA-RLDD (source `{data['source']}`), parts {', '.join(data['parts'])}: {data['subjects_found']} of the dataset's 60 people. "
        f"Phone and webcam recordings, {num(60 * data['hours_of_video'] / data['videos'], 1)} minutes each on average; {data['portrait_videos']} of the "
        f"{data['videos']} are taller than wide. The label is the file name (0, 5, 10) and applies to the whole video.\n"
    )
    add(
        f"- Frames are processed at 15 per second by the videos' own timestamps: {data['processed_frames']} frames in total. "
        f"Processed rate per video: {num(fps['min'], 1)} to {num(fps['max'], 1)} per second (median {num(fps['median'], 1)}); "
        f"some recordings are slower than 15 fps or have a variable rate, and every duration below is measured in seconds, not in frames."
        + (f" Under 12 per second: {', '.join(fps['videos_under_12'])}." if fps["videos_under_12"] else "")
        + "\n"
        f"- **No face** in {pct(no_face['rate_overall'], 2)} of the frames ({no_face['frames']}); per video, median "
        f"{pct(no_face['rate_per_video']['median'], 2)}, worst {pct(no_face['rate_per_video']['max'], 2)}. "
        + (f"Videos above 5 %: {', '.join(no_face['videos_above_5_percent'])}." if no_face["videos_above_5_percent"] else "No video is above 5 %.")
        + " A frame with no face is missing, never a zero.\n"
        f"- **Rotation.** {orientation['videos_with_rotation_flag']} videos carry a rotation flag; OpenCV applies it while decoding. "
        f"The head roll measured on the decoded frames confirms it: the largest median roll of any video is "
        f"{num(orientation['max_abs_median_roll_deg'], 1)} degrees"
        + (f"; sideways videos: {', '.join(orientation['videos_sideways'])}." if orientation["videos_sideways"] else ", so no video is sideways.")
        + "\n"
        f"- **Windows.** {data['window_rule']}\n"
    )
    rows = []
    for state in STATES:
        w = windows["by_state"][state]
        rows.append([STATE_TITLE[state], w["windows"], w["dropped_low_face_or_few_frames"], w["calibration_period"], w["evaluated"]])
    rows.append(["total", windows["windows"], windows["dropped_low_face_or_few_frames"], windows["calibration_period"], windows["evaluated"]])
    add(table(["state", "windows", "dropped (little face or few frames)", "first 120 s of the alert video", "scored"], rows) + "\n")
    if data["subjects_not_used"] or data["incomplete_subjects"] or data["failed_videos"]:
        add("Not used:\n")
        for subject, reason in data["subjects_not_used"].items():
            add(f"- subject {subject}: {reason}")
        for problem in data["incomplete_subjects"]:
            add(f"- {problem}")
        for failure in data["failed_videos"]:
            add(f"- {failure['video']}: {failure['error']}")
        add("")
    else:
        add("Every subject found is used: no video failed and none was left out.\n")

    # ------------------------------------------------------------------ features
    add("## The features and what each one shows\n")
    add(
        f"Seven numbers per window, defined in `{model['feature_module']}` (version {model['features_version']}), which is the file "
        "the browser worker ports. All of them come from the MediaPipe FaceLandmarker output the browser already has, with the same "
        f"model file. Eye closed: {model['eye_closure']['rule']}.\n"
    )
    add(table(["#", "feature", "definition"], [[i + 1, f"`{n}`", metrics["features"]["definitions"][n]] for i, n in enumerate(metrics["features"]["names"])]) + "\n")
    add(
        "The evidence, feature by feature. Nothing is fitted in this table: it is the raw value of each feature on the scored windows, so it "
        "does not depend on the model. An AUC below 0.5 would mean the feature is lower in drowsy windows.\n"
    )
    rows = []
    for feature in metrics["features"]["names"]:
        s, e = stats[feature], evidence[feature]
        higher = e["subjects_higher_in_drowsy_video"]
        rows.append(
            [f"`{feature}`"]
            + [num(s["mean"][state], 3) for state in STATES]
            + [f"{num(e['auc_alert_vs_drowsy'])} ({interval(e['ci95_subject_bootstrap'])})", f"{higher['subjects']} of {higher['of']}", pct(s["missing_share"])]
        )
    add(
        table(
            ["feature", "mean alert", "mean low vigilance", "mean drowsy", "AUC alert vs drowsy (95 % over people)", "people with drowsy video above alert video", "missing"],
            rows,
        )
        + "\n"
    )
    add(
        (f"Clearly above 0.5 on these people: {', '.join(f'`{f}`' for f in carrying)}. " if carrying else "No feature is clearly above 0.5 on these people. ")
        + (f"Not distinguishable from 0.5: {', '.join(f'`{f}`' for f in silent)}. " if silent else "")
        + "All seven stay in the model in this order: features are not pruned after looking at results.\n"
    )
    add(
        f"Assumptions without a registered source: long closure from {constants['long_closure_s']} s; a nod is a drop of {constants['nod_on_deg']:g} degrees "
        f"that ends within {constants['nod_off_deg']:g}; a window needs a face in {pct(constants['min_face_fraction'], 0)} of at least "
        f"{constants['min_window_frames']} frames. None of them was tuned against these results; nothing in the code can prove when they were chosen. "
        "PERCLOS is `fmcsa-1998-perclos`; the yawn detector is the one calibrated on `yawdd`, unchanged.\n"
    )
    checks = metrics["checks"]
    add(
        f"Checks on the real frames: the pitch grows when the chin goes down in {checks['pitch_sign']['videos_with_positive_correlation']} of "
        f"{checks['pitch_sign']['videos']} videos (median correlation with the nose position {num(checks['pitch_sign']['median_correlation'], 2)}). "
        f"The transformation matrix has `[0, 0, 0, 1]` as its last row in {checks['transformation_matrix']['last_row_is_0_0_0_1']} of "
        f"{checks['transformation_matrix']['frames']} frames with a face: row-major in Python, so `M[2][1]` here is `m[6]` in the browser's column-major array.\n"
    )

    # ------------------------------------------------------------------ the model
    add(f"## The shipped model out of fold: `{name}`\n")
    add(confusion(metrics["confusion_matrix"]) + "\n")
    add(
        f"Rows are the true state, columns the predicted one; counts of 60 s windows. Macro F1 {num(metrics['macro_f1'])} "
        f"({interval(ci.get('macro_f1'))}), AUC {num(metrics['auc'])} ({interval(ci.get('auc'))}), accuracy {pct(chosen['accuracy'])} "
        f"({pct_interval(ci.get('accuracy'))}), log loss {num(chosen['log_loss'])} (a model that always says one third each scores 1.099).\n"
    )
    add(
        f"**About the intervals.** {metrics['validation']['correlated_windows']} They are 95 % percentile intervals from "
        f"{chosen['bootstrap_resamples']} resamples of the {people} subjects. They do not include the uncertainty of refitting the model.\n"
    )
    add(
        f"`fatigueScore` ({model['score']['formula']}): mean {num(score['mean_score']['alert'])} on alert windows, "
        f"{num(score['mean_score']['low_vigilance'])} on low vigilance, {num(score['mean_score']['drowsy'])} on drowsy. "
        f"AUC alert vs drowsy {num(score['auc_alert_vs_drowsy'])}, alert vs the other two {num(score['auc_alert_vs_rest'])}, "
        f"drowsy vs the other two {num(score['auc_drowsy_vs_rest'])}; Spearman correlation with the label {num(score['spearman_with_label'], 2)}.\n"
    )
    add(
        f"**The score lives in a narrow band.** Out of fold it runs from {num(score['min'], 2)} to {num(score['max'], 2)}; the middle half of the "
        f"alert windows is {num(score['percentiles']['alert']['p25'], 2)} to {num(score['percentiles']['alert']['p75'], 2)}, of the drowsy ones "
        f"{num(score['percentiles']['drowsy']['p25'], 2)} to {num(score['percentiles']['drowsy']['p75'], 2)}. A rested person does not score near 0: "
        "strong regularisation pulls every prediction towards the shares of the three states in the training windows, and two of the three are not alert. "
        f"The browser's current formula sits near 0 for a rested face (mean {num(b_score['mean_score']['alert'], 3)} on alert windows, "
        f"{num(b_score['mean_score']['drowsy'], 3)} on drowsy), so any threshold written for the old score does not carry over to this one.\n"
    )
    shipped_metrics = configurations[name]
    add(
        f"Regularisation: C is chosen on the training subjects of each fold (grid under \"How it was run\"). "
        f"It took the smallest value of the grid (the strongest shrinkage) in {shipped_metrics['folds_at_smallest_C']} of {len(shipped_metrics['C_by_fold'])} folds. "
        "The grid was not extended after seeing this; a model that wants that much shrinkage is saying the features carry limited signal.\n"
    )
    add(
        f"Whole videos: {video['model']['correct']} of {video['model']['videos']} right ({pct(video['model']['accuracy'])}; "
        f"{video['model']['rule']}).\n"
    )
    add(confusion(video["model"]["confusion_matrix"]) + "\n")

    # ------------------------------------------------------------------ baseline
    add("## Against what the browser ships today\n")
    ordering = metrics["subject_ordering"]
    add(
        f"`faceWorker.ts` computes `{baseline['formula']}`. It was reproduced on the same windows ({baseline['what']})."
        + (" Both use the same eye closure; the model adds blink rate, blink duration, long closures and trained weights." if chosen["eye_method"] == ff.BLENDSHAPE else "")
        + "\n"
    )
    rows = [
        ["AUC alert vs drowsy", f"{num(score['auc_alert_vs_drowsy'])} ({interval(ci.get('score_auc_alert_vs_drowsy'))})", f"{num(b_score['auc_alert_vs_drowsy'])} ({interval(ci.get('baseline_auc_alert_vs_drowsy'))})"],
        ["AUC alert vs the other two", num(score["auc_alert_vs_rest"]), num(b_score["auc_alert_vs_rest"])],
        ["AUC drowsy vs the other two", num(score["auc_drowsy_vs_rest"]), num(b_score["auc_drowsy_vs_rest"])],
        ["Spearman correlation with the label", num(score["spearman_with_label"], 2), num(b_score["spearman_with_label"], 2)],
        ["AUC, 3 states", f"{num(metrics['auc'])} ({interval(ci.get('auc'))})", f"{num(b_model['auc'])} ({interval(ci.get('baseline_as_model_auc'))}) *"],
        ["macro F1, 3 states", num(metrics["macro_f1"]), num(b_model["macro_f1"]) + " *"],
        ["videos right", f"{video['model']['correct']} of {video['model']['videos']}", f"{video['baseline_as_three_class_model']['correct']} of {video['baseline_as_three_class_model']['videos']} *"],
    ]
    for label, field in (("drowsy video scores above the alert one", "drowsy_above_alert"), ("low-vigilance video above the alert one", "low_vigilance_above_alert"), ("drowsy video above the low-vigilance one", "drowsy_above_low_vigilance")):
        m, b = ordering["model_mean_fatigue_score"][field], ordering["baseline_mean_score"][field]
        rows.append([f"people whose {label}", f"{m['subjects']} of {m['of']}", f"{b['subjects']} of {b['of']}"])
    add(table(["measured on the same windows", "model `fatigueScore`", "browser formula"], rows) + "\n")
    add(f"\\* The formula gives one number, not three probabilities. For the three-state rows it was given {b_model['how']}.\n")
    add(
        f"**Is the model better than the formula?** Alert against drowsy: {gap_binary:+.3f} ({interval(gap_binary_ci)}). "
        + ("The interval excludes 0. " if excludes(gap_binary_ci) else f"The interval includes 0: on these {people} people the two cannot be told apart. ")
        + f"Three states: {gap_three:+.3f} ({interval(gap_three_ci)}). "
        + ("The interval excludes 0: the three probabilities order the states better than the formula's single number does." if excludes(gap_three_ci) else "The interval includes 0 here too.")
        + "\n"
    )

    # ------------------------------------------------------------------ per subject
    add("## Person by person\n")
    aucs = sorted(s["score_auc_alert_vs_drowsy"] for s in subjects if s["score_auc_alert_vs_drowsy"] is not None)
    accuracies = sorted(s["accuracy"] for s in subjects)
    below = sum(a < 0.5 for a in aucs)
    add(
        f"Alert-vs-drowsy AUC of the score inside one person: lowest {num(aucs[0])}, median {num(median(aucs))}, "
        f"highest {num(aucs[-1])}; below 0.5 (the score goes the wrong way) in {below} of {len(aucs)} people. Window accuracy per person: "
        f"{pct(accuracies[0])} to {pct(accuracies[-1])}, median {pct(median(accuracies))}.\n"
    )
    rows = []
    for s in subjects:
        predictions = s["video_predictions"]
        rows.append(
            [
                s["subject"],
                " / ".join(str(s["windows"][state]) for state in STATES),
                pct(s["accuracy"]),
                num(s["score_auc_alert_vs_drowsy"]),
                num(s["baseline_auc_alert_vs_drowsy"]),
                " / ".join(num(s["mean_fatigue_score"][state], 2) for state in STATES),
                " / ".join(STATE_TITLE[predictions[state]] if state in predictions else "n/a" for state in STATES),
            ]
        )
    add(
        table(
            ["subject", "windows (alert / low / drowsy)", "window accuracy", "score AUC alert vs drowsy", "browser formula AUC", "mean score (alert / low / drowsy)", "video called (alert / low / drowsy)"],
            rows,
        )
        + "\n"
    )

    # ------------------------------------------------------------------ DROZY
    if dz:
        parts += drozy_section(dz, score)

    # ------------------------------------------------------------------ thresholds
    if metrics.get("thresholds"):
        parts += thresholds_section(metrics["thresholds"])

    # ------------------------------------------------------------------ final model
    add("## The model the browser gets\n")
    final = metrics["final_model"]
    add(
        f"`data/fatigue_model.json` is the shipped configuration refit on all {people} subjects (C = {final['C']:g}). "
        f"The metrics above are the out-of-fold ones, not of this refit. Trained on: {model['trainedOn']}.\n"
    )
    rows = []
    for i, feature in enumerate(model["features"]):
        rows.append([f"`{feature}`", num(model["mean"][i], 4), num(model["std"][i], 4)] + [num(model["coef"][k][i], 3) for k in range(len(STATES))])
    rows.append(["intercept", "", ""] + [num(v, 3) for v in model["intercept"]])
    add(table(["feature", "mean", "std", "weight alert", "weight low vigilance", "weight drowsy"], rows) + "\n")
    add("Weights apply to standardised features, so they compare across features: a positive weight raises that state's probability.\n")
    add("What the browser has to do, per processed frame at 15 fps and then every 10 s:\n")
    steps = [
        "Keep 60 s of per-frame values: time, face found, eye closed, head pitch (`atan2(m[6], m[10])` of the transformation matrix), mouth opening ratio.",
        f"Eye closed: {model['eye_closure']['rule']}"
        + (f" (the same test as {model['eye_closure']['same_as']})." if model["eye_closure"].get("same_as") else "."),
        "Compute the seven features of the window with the definitions above (the unit tests in `data/tests/test_fatigue_features.py` are the examples to replay).",
        f"Skip the window if it has under {constants['min_window_frames']} frames or a face in under {pct(constants['min_face_fraction'], 0)} of them: no score, not a zero.",
        f"Calibration: {model['calibration']['note']}",
        "`z = (x - mean) / std`, with `z = 0` for a missing feature; `p = softmax(intercept + coef . z)`; classes in the order " + ", ".join(model["classes"]) + ".",
        f"`{model['score']['formula']}`.",
    ]
    add("\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps)) + "\n")
    if not needs_calibration:
        add("No EAR, no percentiles and no calibration are needed in the browser. They are documented in the feature module as evaluated alternatives only.\n")

    # ------------------------------------------------------------------ secondary analyses
    add("## Secondary analyses: the evidence behind the decision\n")
    add(
        "Nothing in this section is the shipped model. These are the measurements the team saw before fixing the configuration; they stay in "
        "`make model` so the decision can be re-examined when better data arrives.\n"
    )
    add("### Four combinations on the same windows\n")
    eye = metrics["eye_methods"]
    calibration = eye["ear_calibration"]
    add(
        f"- Eye closure `blendshape`: mean of `eyeBlinkLeft` and `eyeBlinkRight` above {constants['blendshape_closed']}; no calibration.\n"
        f"- Eye closure `ear_p80`: eye aspect ratio (`soukupova-2016-ear`) at or below `floor + {constants['p80_fraction']} * (open - floor)`, i.e. at least "
        f"80 % closed (`fmcsa-1998-perclos`) relative to the person's own open eye, with open = P{constants['ear_open_percentile']:g} and floor = "
        f"P{constants['ear_floor_percentile']:g} of the first 120 s of their alert video.\n"
        "- Features `absolute`: as computed. `calibrated`: minus, per person, the mean of each feature over the first 120 s of their alert video. "
        "**Both `calibrated` and `ear_p80` assume an alert calibration exists for each person.**\n"
    )
    rows = []
    for config, m in configurations.items():
        mark = " **(shipped)**" if config == name else ""
        gap = chosen["auc_minus_other_configurations"].get(config)
        rows.append(
            [
                f"`{config}`{mark}",
                num(m["auc"]),
                num(m["macro_f1"]),
                pct(m["accuracy"]),
                num(m["log_loss"]),
                num(m["score"]["auc_alert_vs_drowsy"]),
                "" if gap is None else f"{-gap['auc_difference']:+.3f} ({interval([-gap['ci95_subject_bootstrap'][1], -gap['ci95_subject_bootstrap'][0]]) if gap['ci95_subject_bootstrap'] else 'n/a'})",
                f"{m['folds_at_smallest_C']} of {len(m['C_by_fold'])}",
            ]
        )
    add(
        table(
            ["eye method / features", "AUC (3 states)", "macro F1", "accuracy", "log loss", "score AUC alert vs drowsy", "3-state AUC minus the shipped one (95 % over people)", "folds at the smallest C"],
            rows,
        )
        + "\n"
    )
    ahead = [config for config, gap in chosen["auc_minus_other_configurations"].items() if gap["ci95_subject_bootstrap"] and gap["ci95_subject_bootstrap"][1] < 0]
    add(
        (
            f"On 3-state AUC {', '.join(f'`{c}`' for c in ahead)} " + ("is" if len(ahead) == 1 else "are") + " ahead of the shipped combination by more than the noise between people. "
            if ahead
            else "No alternative is ahead of the shipped combination by more than the noise between people. "
        )
        + "Every alternative takes something from the person's alert video (an eye threshold, a reference, or both); "
        "\"What a rested calibration is worth\" below measures how much rides on that.\n"
    )
    add("### If the configuration were chosen by a score\n")
    picked = ", ".join(f"`{config}` in {count}" for config, count in nested["picked"].items() if count)
    best = max(configurations, key=lambda c: configurations[c]["auc"])
    add(
        f"Picking the best of the four by out-of-fold AUC would have named `{best}` ({num(configurations[best]['auc'])}) and that number would be "
        f"optimistic. Choosing inside every fold from the training subjects alone picks {picked} folds and scores AUC {num(nested['auc'])}, "
        f"macro F1 {num(nested['macro_f1'])}, alert-vs-drowsy AUC {num(nested['score']['auc_alert_vs_drowsy'])}. The pick changes from fold to fold: "
        "these people do not single out one combination.\n"
    )
    add("### What a rested calibration is worth\n")
    usual, own, blend = sens["threshold_from_alert_video"], sens["threshold_from_scored_video"], sens["blendshape_absolute_same_windows"]
    sens_ci = sens["ci95_subject_bootstrap"]
    add(f"{sens['question']} {sens['how']}\n")
    add(f"{sens['calibrated_features']['what']}\n")
    rows = []
    reference = sens["calibrated_features"]
    for label, block in (
        ("`ear_p80`, threshold from the alert video", usual),
        ("`ear_p80`, threshold from the scored video", own),
        ("`calibrated` features (blendshape), reference from the alert video", reference["reference_from_alert_video"]),
        ("`calibrated` features (blendshape), reference from the scored video", reference["reference_from_scored_video"]),
        ("`blendshape`, `absolute`, no calibration (shipped)", blend),
    ):
        perclos = [pct(block["perclos"][s], 2) for s in STATES] if "perclos" in block else ["", "", ""]
        rows.append([label, num(block["auc"]), num(block["macro_f1"]), num(block["score_auc_alert_vs_drowsy"])] + perclos)
    add(table(["on the same windows", "AUC (3 states)", "macro F1", "score AUC alert vs drowsy"] + [f"PERCLOS {STATE_TITLE[s]}" for s in STATES], rows) + "\n")
    add(
        f"Windows: {' / '.join(str(sens['windows'][s]) for s in STATES)} (alert / low vigilance / drowsy). The browser's formula gets "
        f"{num(sens['browser_formula_same_windows']['score_auc_alert_vs_drowsy'])} alert vs drowsy on them. Alert-video threshold minus scored-video "
        f"threshold: alert-vs-drowsy AUC {num(usual['score_auc_alert_vs_drowsy'] - own['score_auc_alert_vs_drowsy'])} "
        f"({interval(sens_ci.get('score_auc_alert_vs_drowsy_alert_video_minus_own_video'))}), 3-state AUC {num(usual['auc'] - own['auc'])} "
        f"({interval(sens_ci.get('auc_alert_video_minus_own_video'))}). The same difference for the `calibrated` features: alert-vs-drowsy AUC "
        f"{num(reference['reference_from_alert_video']['score_auc_alert_vs_drowsy'] - reference['reference_from_scored_video']['score_auc_alert_vs_drowsy'])} "
        f"({interval(sens_ci.get('calibrated_features_score_auc_alert_vs_drowsy_alert_video_minus_own_video'))}), 3-state AUC "
        f"{num(reference['reference_from_alert_video']['auc'] - reference['reference_from_scored_video']['auc'])} "
        f"({interval(sens_ci.get('calibrated_features_auc_alert_video_minus_own_video'))}).\n"
    )
    add(f"{sens['reading']}\n")
    add(
        f"**The EAR floor is often not a closed eye.** Across people the open level has median {num(calibration['open_median'])} and the floor "
        f"{num(calibration['floor_median'])}; the floor is between {pct(calibration['floor_over_open_range'][0], 0)} and "
        f"{pct(calibration['floor_over_open_range'][1], 0)} of the open level, and above half of it in "
        f"{calibration['subjects_with_floor_above_half_open']} of {calibration['subjects']} people. The likely reason (not checked frame by frame): "
        "two rested minutes at 15 frames per second hold too few fully closed frames for the 1st percentile to reach one. For those people the rule "
        "fires on a half-closed eye. A calibration that asks the person to close their eyes for a moment would measure the floor directly; that was not tested.\n"
    )
    add(f"{eye['caveat']}\n")
    ear_check = checks["ear_landmarks"]
    add(
        "The six EAR points of each eye sit where the formula assumes (lid points between the corners in "
        f"{pct(ear_check['right']['lid_points_between_corners'], 2)} / {pct(ear_check['left']['lid_points_between_corners'], 2)} of the frames, "
        f"right / left eye; upper lid above lower lid in {pct(ear_check['right']['upper_lid_above_lower_lid_in_image'], 2)} / "
        f"{pct(ear_check['left']['upper_lid_above_lower_lid_in_image'], 2)}), so the indices are not the problem.\n"
    )

    # ------------------------------------------------------------------ limits
    add("## Limits\n")
    limits = [
        "**Self-reported labels.** Each person rated their own state once for the whole video. Nobody measured their alertness, and a rating of 5 or 10 does not mean every minute of the video looks drowsy. This caps what any model can score here.",
        "**Not a controlled vigil.** One recording per state per person, on their own phone or webcam. Nothing shows how drowsy a person was beyond their own label. It is not a work shift and not a crew.",
        f"**{people} people.** These are {data['subjects_found']} of the dataset's 60 (the parts downloaded so far). The intervals are wide because of it.",
        "**Correlated windows.** Thousands of windows come from a few dozen videos; a window count is not a sample size. The intervals resample people.",
        "**Three separate recordings per person**, often with another device, distance, light or camera angle. Part of what separates the states may be the recording, not the person. This applies to the shipped model too, not only to the calibrated alternatives.",
        f"**Phone and laptop geometry.** {data['portrait_videos']} of the {data['videos']} videos are taller than wide, which a laptop webcam never is; the demo is a laptop webcam. Head pitch and the blendshapes change with the camera angle. Glasses and lighting change the eye measurements.",
        f"**Frame rate.** At 15 frames per second a blink is a handful of frames: its duration moves in steps of about 67 ms and the shortest blinks can be missed. {len(data['processed_fps']['videos_under_13'])} videos could only be processed at under 13 frames per second, where the steps are longer.",
        f"**The first 120 s of every alert video are left out** of training and scoring, because the alternatives calibrate on them; the other two videos keep theirs. The shipped model would not need that, and the three states therefore have unequal window counts ({windows['by_state']['alert']['evaluated']} / {windows['by_state']['low_vigilance']['evaluated']} / {windows['by_state']['drowsy']['evaluated']}).",
        "**Assumptions.** The 0.5 s long-closure boundary, the nod levels and the window rule have no registered source. They were not tuned against these results.",
        "**Yawns** use a detector calibrated on acted yawns of drivers (YawDD). Nobody labelled yawns in RLDD, so its counts here are unchecked.",
        (
            "**Reaction time only on DROZY**, which is near-infrared video of 14 people with no interval computed; RLDD has no PVT. See the DROZY section for its own limits."
            if dz
            else "**No reaction-time ground truth.** `pvt_correlation` is null until DROZY is available."
        ),
        "**Not validated for spaceflight**, and head nods rely on gravity: in microgravity we expect the eye features to carry the signal (our hypothesis, no source).",
    ]
    add("\n".join(f"- {text}" for text in limits) + "\n")

    # ------------------------------------------------------------------ reproduction
    add("## How it was run\n")
    per_video = extraction["decode_plus_mediapipe_seconds_per_video"]
    runs = extraction["runs"]
    run_text = "; ".join(f"{r['videos']} videos in {r['wall_seconds'] / 60:.1f} min with {r['workers']} processes" for r in runs) or "n/a"
    add(
        f"- `make model` = `cd data && uv run python pipeline.py`. MediaPipe runs once per video and is cached in `data/features/rldd/` (git-ignored, "
        "coordinates and scores only: no frame or image is written anywhere). A second run reads the cache.\n"
        f"- FaceLandmarker `{extraction['face_landmarker']['model_file_name']}` (sha256 `{extraction['face_landmarker']['model_sha256'][:16]}...`), the file the browser loads; "
        f"VIDEO mode, one face, confidences {extraction['face_landmarker']['min_face_detection_confidence']}.\n"
        f"- MediaPipe time: {num(extraction['mediapipe_ms_per_frame_mean'], 1)} ms per frame on average; decoding plus MediaPipe took "
        f"{num(per_video['min'], 0)} to {num(per_video['max'], 0)} s per video (median {num(per_video['median'], 0)} s), "
        f"{num(extraction['decode_plus_mediapipe_seconds_sum'] / 3600, 2)} h summed over videos. Extraction runs: {run_text}. "
        f"{extraction['note']}\n"
        f"- Validation: {metrics['validation']['scheme']}; {metrics['validation']['inner']}; seed {metrics['validation']['seed']}. "
        "The scaler, C and the weights never see the test subject. The configuration is a constant of the pipeline (`SHIPPED`), not an output of it.\n"
        + (
            "- DROZY: the same extractor and window code, with DROZY's own frame times; `fatigue_model.json` applied unchanged. Nothing from DROZY is cached "
            "(its licence): every run extracts it again, and only aggregate numbers are written. Without RLDD on the machine, `make model` validates the "
            "existing model on DROZY and merges the result into `metrics.json` and this report, leaving the model and the RLDD numbers unchanged.\n"
            if dz
            else ""
        )
    )

    # ------------------------------------------------------------------ every video
    add("## Every video\n")
    rows = []
    for v in metrics["videos"]:
        rows.append(
            [
                v["subject"],
                v["label"],
                f"{v['width']}x{v['height']}",
                num(v["source_fps"], 1),
                f"{v['orientation_meta_deg']:g}",
                num(v["roll_median_deg"], 1),
                num(v["duration_s"], 0),
                num(v["processed_fps"], 1),
                pct(v["no_face_rate"], 2),
                num(v["longest_no_face_s"], 1),
                f"{v['windows_evaluated']} of {v['windows']}",
            ]
        )
    add(
        table(
            ["subject", "label", "decoded size", "source fps", "rotation flag", "median head roll (deg)", "seconds", "processed per second", "no face", "longest no-face (s)", "windows scored"],
            rows,
        )
        + "\n"
    )
    add("In an alert video (label 0) the windows that touch the first 120 s are left out (see \"Limits\").\n")
    return "\n".join(parts)
