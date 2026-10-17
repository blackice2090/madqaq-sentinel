# Presentation — Results Slide (one slide)

**Headline:** Dual-channel reasoning improved procedure-integrity detection in the frozen synthetic benchmark.

**Comparison** (frozen 1,200-journey synthetic benchmark; archived values from `docs/evaluation/final/system_comparison.csv`):

| System | Exact violation-set accuracy | Macro-F1 | Violated journeys without an alarm |
|---|---|---|---|
| FULL DUAL-CHANNEL | 0.950 | 0.981 | 0 / 812 |
| PHYSICAL ONLY (internal ablation) | 0.517 | 0.395 | 140 / 812 |
| DIGITAL ONLY (internal ablation) | 0.567 | 0.440 | 231 / 812 |
| SIMPLE CHECK (rule baseline) | 0.567 | 0.500 | 368 / 812 |

**Speaker line:** "Only the dual-channel configuration detected phantom completion and channel contradiction. Physical-only and digital-only are internal ablations of our own engine, not competing products."

**Limitation footer (keep on slide):** Primary limitation: 60 low-confidence physical-evidence cases caused false phantom-completion alerts.

**Scope footer (keep on slide):** Synthetic procedure-integrity benchmark; digital channel simulated; not a measure of live-camera or field accuracy.

Rules: never show "95% accuracy" without "exact violation-set" and "frozen synthetic benchmark"; no other percentages beyond the table. Claims: C002, C003, C005, C008, C009.
