"""M6.1 web backend constants. Defaults are starting points for a LOCAL demo, not tuned values."""
from __future__ import annotations

import os

PROTOCOL_VERSION = "madqaq-web/1"

# ---- transport limits -------------------------------------------------------
MAX_FRAME_BYTES = 2_000_000        # largest accepted binary JPEG message
MAX_TEXT_BYTES = 4_096             # largest accepted JSON command message
MAX_FRAME_WIDTH = 1920             # decoded-size limits, checked from the JPEG header BEFORE decoding
MAX_FRAME_HEIGHT = 1920
MAX_SESSIONS = 4                   # concurrent browser sessions (each has its own tracker/model)
TIMELINE_LIMIT = 10                # timeline rows sent with each state

# ---- client hints (the browser owns sampling; these are only advertised defaults) ----
RECOMMENDED_SAMPLE_FPS = 6
RECOMMENDED_MAX_WIDTH = 960
RECOMMENDED_JPEG_QUALITY = 0.75

# ---- origins -----------------------------------------------------------------
DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def allowed_origins() -> tuple[str, ...]:
    """Localhost frontend origins only, unless MADQAQ_WEB_ORIGINS (comma-separated) overrides them."""
    raw = os.environ.get("MADQAQ_WEB_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_ALLOWED_ORIGINS
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip() and o.strip() != "*")


# ---- wording (disclosures shown by the web UI) ---------------------------------
SIM_NOTE = "Local simulator — not a production checkpoint integration."
FRAMES_NOTE = ("Sampled camera frames are sent to the local MADQAQ analysis backend while "
               "the web demo is active.")
FRAMES_STORAGE_NOTE = "Frames are analysed in memory and are not saved."
