from __future__ import annotations

import argparse

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import JourneyStatus
from simulator.scenarios import SCENARIOS, scenario


def summarize(result):
    if result.violations:
        v = result.violations[0]
        return f"{v.type.value}:{v.step_id}"
    if result.overall_status == JourneyStatus.COMPLETED:
        return "CONFORMANT"
    return result.overall_status.value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    args = parser.parse_args()

    proc, journey, physical, digital, expected = scenario(args.scenario)
    result = ConformanceEngine().evaluate(proc, journey, physical, digital)
    actual = summarize(result)

    print(f"Scenario: {args.scenario}")
    print("Expected procedure: A → B → C → D")
    print("Physical trace:    ", " → ".join(e.step_id for e in physical))
    print("Digital trace:     ", " → ".join(e.step_id for e in digital))
    print(f"Expected result: {expected}")
    print(f"Engine output:   {actual}")
    print(f"Match:           {'YES' if actual == expected else 'NO'}")
    if result.violations:
        print(f"Explanation:     {result.violations[0].message}")


if __name__ == "__main__":
    main()
