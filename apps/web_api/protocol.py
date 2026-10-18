"""WebSocket protocol for the M6.1 web dashboard (see docs/M6_WEB_DASHBOARD.md).

Client -> server
  binary : one JPEG camera frame
  text   : {"command": "<name>"}  with <name> in COMMANDS (no other fields are accepted)

Server -> client (JSON text, always with a "type")
  hello | state | ack | error | pong | evidence
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass

from apps.web_api import config

# command -> M2 digital preset id (None for non-preset commands)
COMMANDS: dict[str, str | None] = {
    "reset": None,
    "digital_full": "full_trace",
    "digital_without_b": "without_b",
    "digital_b_failed": "b_failed",
    "digital_clear": None,
    "ping": None,
    "get_evidence": None,
}


class ProtocolError(Exception):
    """Client error. `code` and the message are safe to send back to the client."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Command:
    name: str

    @property
    def preset_id(self) -> str | None:
        return COMMANDS[self.name]


def parse_command(text: str) -> Command:
    if len(text.encode("utf-8", errors="replace")) > config.MAX_TEXT_BYTES:
        raise ProtocolError("message_too_large", f"Command messages are limited to {config.MAX_TEXT_BYTES} bytes.")
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        raise ProtocolError("invalid_json", "Command must be a JSON object such as {\"command\": \"reset\"}.") from None
    if not isinstance(data, dict) or set(data) != {"command"}:
        raise ProtocolError("invalid_command", "Command must be exactly {\"command\": \"<name>\"}.")
    name = data["command"]
    if not isinstance(name, str) or name not in COMMANDS:
        raise ProtocolError("invalid_command", "Unknown command. Allowed: " + ", ".join(COMMANDS) + ".")
    return Command(name)


# ---- JPEG validation -----------------------------------------------------------
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """(width, height) read from the JPEG frame header, without decoding pixels.

    Raises ProtocolError for anything that is not a well-formed JPEG header.
    """
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        raise ProtocolError("invalid_image", "Binary messages must be JPEG images.")
    i, n = 2, len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            raise ProtocolError("invalid_image", "Malformed JPEG header.")
        marker = data[i + 1]
        if marker == 0xFF:          # fill byte
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker in (0xD9, 0xDA):  # end of image / start of scan before any frame header
            break
        (seg_len,) = struct.unpack(">H", data[i + 2:i + 4])
        if seg_len < 2:
            raise ProtocolError("invalid_image", "Malformed JPEG header.")
        if marker in _SOF_MARKERS:
            if i + 9 > n:
                break
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            if width == 0 or height == 0:
                raise ProtocolError("invalid_image", "JPEG has zero width or height.")
            return width, height
        i += 2 + seg_len
    raise ProtocolError("invalid_image", "JPEG frame header not found.")


def validate_frame(data: bytes) -> tuple[int, int]:
    if len(data) > config.MAX_FRAME_BYTES:
        raise ProtocolError("frame_too_large", f"Frames are limited to {config.MAX_FRAME_BYTES} bytes.")
    w, h = jpeg_dimensions(data)
    if w > config.MAX_FRAME_WIDTH or h > config.MAX_FRAME_HEIGHT:
        raise ProtocolError(
            "frame_too_large",
            f"Frames are limited to {config.MAX_FRAME_WIDTH}x{config.MAX_FRAME_HEIGHT} pixels; got {w}x{h}.")
    return w, h


def error_message(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}
