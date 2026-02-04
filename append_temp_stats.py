#!/usr/bin/env python3
"""
Parse a DS18B20-style temperature log and append summary statistics to the file.

Expected line format (example):
2026-01-10T16:48:20 | DS18B20: 20.62 °C
"""

from __future__ import annotations

import argparse
import math
import re
from datetime import datetime
from statistics import mean, median

TEMP_RE = re.compile(r":\s*([-+]?\d+(?:\.\d+)?)\s*°\s*[CF]\b")

def stddev_population(values: list[float]) -> float:
    """Population standard deviation (divide by N)."""
    if not values:
        return float("nan")
    mu = mean(values)
    return math.sqrt(sum((x - mu) ** 2 for x in values) / len(values))

def stddev_sample(values: list[float]) -> float:
    """Sample standard deviation (divide by N-1)."""
    if len(values) < 2:
        return float("nan")
    mu = mean(values)
    return math.sqrt(sum((x - mu) ** 2 for x in values) / (len(values) - 1))

def parse_temperatures(path: str) -> list[float]:
    temps: list[float] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = TEMP_RE.search(line)
            if m:
                try:
                    temps.append(float(m.group(1)))
                except ValueError:
                    # Skip malformed numbers
                    pass
    return temps

def format_summary(values: list[float], *, use_sample_stddev: bool) -> str:
    if not values:
        return (
            "\n\n=== Temperature Summary ===\n"
            f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
            "No temperature readings were found.\n"
        )

    sd = stddev_sample(values) if use_sample_stddev else stddev_population(values)
    sd_label = "Sample (N-1)" if use_sample_stddev else "Population (N)"

    return (
        "\n\n=== Temperature Summary ===\n"
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Number of data points: {len(values)}\n"
        f"Min temperature: {min(values):.2f} °C\n"
        f"Max temperature: {max(values):.2f} °C\n"
        f"Mean temperature: {mean(values):.2f} °C\n"
        f"Median temperature: {median(values):.2f} °C\n"
        f"Standard deviation ({sd_label}): {sd:.4f} °C\n"
    )

def main() -> int:
    ap = argparse.ArgumentParser(description="Append temperature summary stats to a log file.")
    ap.add_argument("file", help="Path to the .txt log file")
    ap.add_argument(
        "--sample-stddev",
        action="store_true",
        help="Use sample standard deviation (divide by N-1). Default is population (divide by N).",
    )
    args = ap.parse_args()

    temps = parse_temperatures(args.file)
    summary = format_summary(temps, use_sample_stddev=args.sample_stddev)

    with open(args.file, "a", encoding="utf-8") as f:
        f.write(summary)

    print("Appended summary to:", args.file)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())