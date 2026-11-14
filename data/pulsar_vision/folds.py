"""Subject-grouped folds for leave-subject-out validation."""

from __future__ import annotations

import random
from typing import Iterable, Mapping


def grouped_folds(
    subject_strata: Mapping[str, str],
    n_folds: int,
    seed: int,
) -> list[list[str]]:
    """Split subjects into ``n_folds`` disjoint test folds.

    ``subject_strata`` maps each subject id to a stratum (here: sex), so that every fold
    gets a similar share of each stratum. The split is deterministic for a given seed:
    subjects are sorted, shuffled within their stratum and dealt round-robin.
    Each subject lands in exactly one fold; all the videos of a subject follow it.
    """
    subjects = sorted(subject_strata)
    if n_folds < 2:
        raise ValueError("at least 2 folds are needed")
    if len(subjects) < n_folds:
        raise ValueError(f"{len(subjects)} subjects cannot fill {n_folds} folds")
    rng = random.Random(seed)
    folds: list[list[str]] = [[] for _ in range(n_folds)]
    position = 0
    for stratum in sorted(set(subject_strata.values())):
        members = [s for s in subjects if subject_strata[s] == stratum]
        rng.shuffle(members)
        for subject in members:
            folds[position % n_folds].append(subject)
            position += 1
    return [sorted(fold) for fold in folds]


def train_subjects(folds: list[list[str]], test_fold: int) -> list[str]:
    return sorted(s for i, fold in enumerate(folds) if i != test_fold for s in fold)


def assert_disjoint(folds: Iterable[Iterable[str]]) -> None:
    """Raise if any subject appears in more than one fold."""
    seen: dict[str, int] = {}
    for index, fold in enumerate(folds):
        for subject in fold:
            if subject in seen:
                raise AssertionError(f"subject {subject} is in folds {seen[subject]} and {index}")
            seen[subject] = index
