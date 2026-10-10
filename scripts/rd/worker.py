"""Built-in deterministic CSV pilot worker.  It intentionally has no script hook."""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path


def _number(value):
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError("non-finite numeric value")
    return number


def _percentile(values, q):
    if not values: raise ValueError("empty bootstrap")
    values = sorted(values)
    at = (len(values) - 1) * q
    low, high = int(at), min(len(values) - 1, int(at) + 1)
    return values[low] + (values[high] - values[low]) * (at - low)


def _bootstrap(a, b, seed, count, paired=False):
    rng = random.Random(seed)
    values = []
    for _ in range(count):
        if paired:
            differences = [b[i] - a[i] for i in range(len(a))]
            values.append(statistics.fmean([differences[rng.randrange(len(differences))] for _ in differences]))
        else:
            aa = [a[rng.randrange(len(a))] for _ in a]
            bb = [b[rng.randrange(len(b))] for _ in b]
            values.append(statistics.fmean(bb) - statistics.fmean(aa))
    return _percentile(values, .025), _percentile(values, .975)


def run(protocol):
    params = protocol["parameters"]
    method = protocol["method"]
    path = Path(protocol["data_path"])
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for index, row in enumerate(csv.DictReader(stream), 2):
            if index > 100001: raise ValueError("sample row limit exceeded")
            rows.append(row)
    count = int(params.get("bootstrap", 0))
    if count < 1 or count > 2000: raise ValueError("bootstrap must be in 1..2000")
    if method == "group_difference":
        group, value = params["group_column"], params["value_column"]
        control, treatment = params["control"], params["treatment"]
        a = [_number(row[value]) for row in rows if row.get(group) == control]
        b = [_number(row[value]) for row in rows if row.get(group) == treatment]
    elif method == "paired_difference":
        before, after = params["before_column"], params["after_column"]
        a = [_number(row[before]) for row in rows]
        b = [_number(row[after]) for row in rows]
        if len(a) != len(b): raise ValueError("paired columns have different lengths")
    else:
        raise ValueError("unsupported built-in pilot method")
    if not a or not b: raise ValueError("both comparison groups need rows")
    effect = statistics.fmean(b) - statistics.fmean(a)
    low, high = _bootstrap(a, b, int(protocol["seed"]), count, paired=(method == "paired_difference"))
    threshold = float(params["min_effect"])
    if low > threshold: interpretation = "POSITIVE"
    elif high < threshold: interpretation = "NEGATIVE"
    else: interpretation = "INCONCLUSIVE"
    return {"interpretation": interpretation,
            "measurement": {"effect": effect, "ci_low": low, "ci_high": high,
                            "n_control": len(a), "n_treatment": len(b),
                            "min_effect": threshold, "bootstrap": count}}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1: raise ValueError("worker requires one protocol JSON")
    protocol = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    print(json.dumps(run(protocol), ensure_ascii=False, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        raise SystemExit(2)
