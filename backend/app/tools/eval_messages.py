"""How well messages are understood, per label, on the labelled set: the rules always, and the model and the
reconciled decision when a model key is set. Not run in CI: with a key it calls the provider once per message.

    python -m app.tools.eval_messages [path/to/messages.jsonl]

A reconciled decision that asks the consumer about the right complaint type counts as right: they confirm with
one tap. Messages are printed only when they are misread, and they are synthetic.
"""

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

from app.config import get_settings
from app.domain.conversation.intents import classify
from app.flows.understand import reconcile
from app.services import llm

DEFAULT = Path(__file__).resolve().parents[2] / "tests" / "data" / "messages.jsonl"
MAX_ROWS = 1000


def _right(label: str, got: str) -> bool:
    return got in (label, f"confirm:{label}")


async def _score(rows: list[dict[str, str]], with_model: bool) -> dict[str, dict[str, list[bool]]]:
    scores: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        label, rules = row["label"], classify(row["text"])
        scores[label]["rules"].append(rules.label == label)
        if not with_model:
            continue
        model = await llm.classify(row["text"])
        decided = reconcile(rules, model)
        scores[label]["model"].append(model is not None and model.label == label)
        scores[label]["combined"].append(_right(label, decided.label))
        if not _right(label, decided.label):
            print(f"  misread [{label} -> {decided.label}] {row['text']}")
    return scores


def _report(scores: dict[str, dict[str, list[bool]]], columns: list[str]) -> None:
    print(f"{'label':<22}{'n':>4}" + "".join(f"{c:>10}" for c in columns))
    totals: dict[str, list[bool]] = defaultdict(list)
    for label in sorted(scores):
        row = scores[label]
        cells = "".join(f"{sum(row[c]) / len(row[c]):>10.0%}" for c in columns)
        print(f"{label:<22}{len(row['rules']):>4}{cells}")
        for c in columns:
            totals[c] += row[c]
    print(f"{'all':<22}{len(totals['rules']):>4}" + "".join(f"{sum(totals[c]) / len(totals[c]):>10.1%}"
                                                          for c in columns))


def main(path: Path) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][:MAX_ROWS]
    with_model = bool(get_settings().openai_api_key)
    if not with_model:
        print("No model key set: rules only.")
    scores = asyncio.run(_score(rows, with_model))
    _report(scores, ["rules", "model", "combined"] if with_model else ["rules"])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
