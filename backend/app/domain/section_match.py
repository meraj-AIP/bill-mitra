"""Which mapped sections an unmapped printed name most likely is. String similarity only, nothing decided: a
units manager still maps the name."""

from difflib import SequenceMatcher

# Spelling variants of one place score 0.85 and up; different places with a shared suffix sit near 0.65
# (Kondapur and Isnapur 0.67), and a wrong one-click map sends cases to the wrong AE.
MIN_SCORE = 0.8
TOP = 3


def closest(norm: str, candidates: list[tuple[str, str, str]]) -> list[tuple[str, str, float]]:
    """candidates: (section id, section name, normalised name or alias). Best score per section, top three."""
    best: dict[str, tuple[str, float]] = {}
    matcher = SequenceMatcher(autojunk=False)
    matcher.set_seq2(norm)
    for section_id, name, other in candidates:
        matcher.set_seq1(other)
        # The cheap upper bounds skip most names before the full ratio, as difflib.get_close_matches does.
        if matcher.real_quick_ratio() < MIN_SCORE or matcher.quick_ratio() < MIN_SCORE:
            continue
        score = matcher.ratio()
        if score >= MIN_SCORE and score > best.get(section_id, ("", 0.0))[1]:
            best[section_id] = (name, score)
    ranked = sorted(best.items(), key=lambda item: (-item[1][1], item[1][0]))[:TOP]
    return [(section_id, name, round(score, 2)) for section_id, (name, score) in ranked]
