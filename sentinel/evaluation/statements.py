"""Mandatory scope wording used verbatim in every generated report and in the docs."""

SYNTHETIC_SCOPE = (
    "This benchmark uses procedurally generated synthetic event sequences. "
    "It evaluates deterministic procedure-integrity reasoning, not live-camera accuracy or field performance."
)
ABLATION_SCOPE = "The physical-only and digital-only systems are internal ablations, not external commercial baselines."
CI_SCOPE = ("Confidence intervals are bootstrap statistical intervals over this synthetic benchmark sample; "
            "they are not field-performance confidence intervals.")
LATENCY_SCOPE = ("Latency is engine evaluation latency only: it measures the time to evaluate evidence that already exists "
                 "as events and excludes camera capture, YOLO detection, tracking and UI rendering. It is not end-to-end "
                 "latency and it is specific to the machine that measured it.")
DEV_STATUS = ("This report covers the DEVELOPMENT split only. The FINAL split has been generated but no system has been "
              "evaluated on it.")

FINAL_STATUS = ("This report covers the FINAL split: the frozen benchmark (seed 20261123), evaluated once with the frozen M4.1 "
                "systems and metric definitions. No engine, oracle, generator, threshold or case was changed after the results were observed.")
LATENCY_LABEL = ("Engine evaluation latency only. This excludes camera capture, YOLO inference, tracking, UI rendering, "
                 "and external-system latency.")

FORBIDDEN_PHRASES = ("proves superiority", "outperforms all", "production ready", "production-ready")

KNOWN_LIMITATION = (
    "Known development-set limitation: when a procedure step is physically observed only below the configured confidence threshold but is correctly recorded by the digital channel, the current engine may classify the digital completion as PHANTOM_COMPLETION rather than UNCERTAIN. In the development benchmark this occurred in 15 weak-physical-evidence cases. No engine or oracle changes were made after observing this result."
)
KNOWN_LIMITATION_NOTE = "This represents conservative evidence handling and has not been validated as an operationally optimal policy."
