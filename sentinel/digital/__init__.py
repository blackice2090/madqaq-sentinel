"""M2 digital channel: a LOCAL SIMULATOR for demonstration. Not a real checkpoint-system integration."""
from sentinel.digital.presets import (
    B_FAILED, FULL_TRACE, PRESETS, PRESETS_BY_KEY, WITHOUT_B, DigitalPreset,
)
from sentinel.digital.simulator import SIMULATOR_SOURCE, DigitalEventSimulator

__all__ = [
    "B_FAILED", "FULL_TRACE", "PRESETS", "PRESETS_BY_KEY", "WITHOUT_B", "DigitalPreset",
    "SIMULATOR_SOURCE", "DigitalEventSimulator",
]
