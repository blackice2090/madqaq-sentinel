# Finalist Claims Cheatsheet

One page. Source of truth: [`CLAIMS_REGISTRY.md`](CLAIMS_REGISTRY.md). Positioning: **research prototype · working proof of concept · finalist demonstration prototype.**

## SAFE TO SAY

- "MADQAQ Sentinel cross-checks physical observations with digital procedure records to detect procedure-integrity inconsistencies." (C008, C010, C011)
- "The prototype converts live camera observations into temporary physical procedure events." (C010)
- "The prototype demonstrates live physical evidence combined with a SIMULATED DIGITAL CHANNEL." (C011)
- "It uses temporary journey tracking and does not require face recognition or persistent identity." (C012)
- "The benchmark has 1,200 frozen, procedurally generated synthetic journeys." (C001)
- "We report a known limitation openly: weak physical evidence." (C009)

## USE WITH SCOPE (always add: frozen synthetic benchmark)

- "On a frozen 1,200-journey synthetic benchmark, it achieved 95.0% exact violation-set accuracy and 0.981 Macro-F1." (C002, C003)
- "Macro-F1 0.981, 95% bootstrap CI 0.976–0.986." (C003)
- "Micro-F1 0.973." (C004)
- "All 812 violated journeys raised an alarm (0 of 812 without an alarm) in the frozen synthetic benchmark." (C005)
- "Phantom completion: recall 1.000, precision 0.860, F1 0.925 on the frozen synthetic benchmark." (C006)
- "Channel contradiction: precision/recall/F1 1.000 within the frozen synthetic benchmark." (C007)
- "Internal ablations show that cross-channel reasoning detected phantom completion and channel contradiction that single-channel variants and the simple check did not." (C008)
- "ENGINE EVALUATION ONLY: tens of microseconds per case in the recorded benchmark environment." (C013)
- "The frozen final split, independently seeded but from the same procedural distribution and composition design, reproduced the development metrics closely." (C014)
- "Primary limitation: 60 low-confidence physical-evidence cases caused false phantom-completion alerts; this reflects conservative evidence handling and has not been validated as operationally optimal." (C009)

## DO NOT SAY

- Do not say: "The system is 98.1% accurate." / "98.1% detection accuracy" (0.981 is Macro-F1).
- Do not say: "The camera detects violations with 95% accuracy." / "95% system accuracy" / "95% real-world accuracy".
- Do not say: "The digital channel is connected to a live checkpoint system." / "real government checkpoint database" / "production border systems integration".
- Do not say: "100% of real security violations are detected." / "100% detection rate in the field."
- Do not say: "Perfect phantom-completion detection."
- Do not say: "MADQAQ beats all competing systems." (Physical-only and digital-only are internal ablations, not competitors.)
- Do not say: "Tested on 1,200 real passengers." / "validated on 1,200 checkpoint operations."
- Do not say: "Independent real-world validation." / "out-of-distribution validation."
- Do not say: "System latency", "camera latency" or "end-to-end latency" for the microsecond figure.
- Do not say: "production ready", "field validated", "deployment ready", "government approved", "operationally proven."
