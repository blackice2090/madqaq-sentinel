"""Finalist dashboard: pure layout (testable, no camera) + Pillow painter.

layout_dashboard() turns a DashboardModel into positioned text/rect ops for a given canvas size
and guarantees by construction that single-line text is shrunk/ellipsized to fit its container
and multi-line text is wrapped, so nothing is clipped with whatever font the machine provides.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageDraw

from apps.finalist_demo.fonts import FontKit
from sentinel.presentation import labels
from sentinel.presentation.model import DashboardModel
from sentinel.vision.pipeline import PersonView
from sentinel.vision.zones import ZoneSet

Rect = tuple[int, int, int, int]
GREEN = (14, 63, 60)        # #0E3F3C deep green
CREAM = (247, 241, 231)     # #F7F1E7
ORANGE = (217, 120, 74)     # #D9784A


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]


CARD = mix(GREEN, CREAM, 0.10)
CARD_DARK = mix(GREEN, (0, 0, 0), 0.30)
MUTED = mix(GREEN, CREAM, 0.72)


@dataclass
class Op:
    kind: str                      # "text" | "rect"
    rect: Rect
    text: str = ""
    size: int = 0
    bold: bool = False
    color: tuple[int, int, int] = CREAM
    fill: tuple[int, int, int] | None = None
    outline: tuple[int, int, int] | None = None
    alpha: int = 255
    container: Rect | None = None  # text must lie inside this
    radius: int = 0


@dataclass
class Layout:
    width: int
    height: int
    scale: float
    ops: list[Op] = field(default_factory=list)
    camera_box: Rect = (0, 0, 0, 0)
    footer_top: int = 0
    right_bottom: int = 0
    left_bottom: int = 0

    def texts(self) -> list[Op]:
        return [o for o in self.ops if o.kind == "text"]

    def all_text(self) -> str:
        return "\n".join(o.text for o in self.texts())


class _Builder:
    def __init__(self, kit: FontKit, W: int, H: int):
        self.kit, self.W, self.H = kit, W, H
        self.s = min(W / 1600, H / 900)
        self.out = Layout(W, H, self.s)

    def S(self, v: float) -> int:
        return max(1, round(v * self.s))

    def rect(self, r: Rect, fill=None, outline=None, alpha=255, radius=0) -> None:
        self.out.ops.append(Op("rect", r, fill=fill, outline=outline, alpha=alpha, radius=radius))

    def text(self, x: int, y: int, s: str, size: float, color=CREAM, bold=False, max_w: int | None = None,
             container: Rect | None = None, align: str = "left", min_size: int = 11) -> Rect:
        """Add one line of text, shrunk then ellipsized to fit max_w. Returns its bounding rect."""
        kit = self.kit
        s = kit.txt(s)
        size = max(min_size, round(size))
        if max_w is not None:
            while kit.width(s, size, bold) > max_w and size > min_size:
                size -= 1
            while kit.width(s, size, bold) > max_w and len(s) > 1:
                s = s[:-2].rstrip() + kit.txt("…")
        w = int(kit.width(s, size, bold)) + 1
        h = kit.height(size, bold)
        if align == "right":
            x = x - w
        elif align == "center":
            x = x - w // 2
        r = (x, y, x + w, y + h)
        self.out.ops.append(Op("text", r, text=s, size=size, bold=bold, color=color, container=container))
        return r

    def wrap(self, x: int, y: int, s: str, size: float, max_w: int, max_lines: int, color=CREAM, bold=False,
             container: Rect | None = None, line_gap: int = 4) -> int:
        """Word-wrap into at most max_lines lines; returns the y below the block."""
        kit = self.kit
        size = round(size)
        words = kit.txt(s).split()
        lines: list[str] = []
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if kit.width(trial, size, bold) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1] + kit.txt("…")
        for line in lines:
            r = self.text(x, y, line, size, color, bold, max_w=max_w, container=container)
            y = r[3] + line_gap
        return y


def layout_dashboard(model: DashboardModel, W: int, H: int, kit: FontKit | None = None, notice: str = "") -> Layout:
    kit = kit or FontKit()
    b = _Builder(kit, W, H)
    S, out = b.S, b.out
    m = S(24)
    header_h = S(76)
    footer_h = S(88)
    footer_top = H - footer_h
    out.footer_top = footer_top
    content_top = header_h + S(14)
    content_bottom = footer_top - S(8)
    left_w = round((W - 3 * m) * 0.48)
    right_x = 2 * m + left_w
    right_w = W - m - right_x
    left_x = m
    full = (0, 0, W, H)

    # ---- header
    b.rect((0, 0, W, header_h), fill=CARD_DARK)
    tr = b.text(m, S(6), "MADQAQ Sentinel", S(34), CREAM, True, max_w=round(W * 0.5), container=(0, 0, W, header_h))
    b.text(m, tr[3], "Procedure Integrity Monitor", S(19), ORANGE, False, max_w=round(W * 0.5), container=(0, 0, W, header_h))
    jtxt = f"Journey {model.journey_short}" if model.has_journey else "No active journey"
    b.text(W - m, S(26), jtxt, S(19), CREAM, False, max_w=round(W * 0.35), container=(0, 0, W, header_h), align="right")

    label_h = S(18)
    gap = S(10)

    def section(x: int, y: int, w: int, title: str) -> int:
        b.text(x, y, title, S(15), ORANGE, True, max_w=w, container=(x, y, x + w, y + label_h + 4))
        return y + label_h + S(4)

    # ---- left column: camera + timeline
    y = content_top
    y = section(left_x, y, left_w, "LIVE CAMERA / PHYSICAL CHANNEL")
    cam_h = round(left_w * 9 / 16)
    cam = (left_x, y, left_x + left_w, y + cam_h)
    out.camera_box = cam
    b.rect(cam, fill=CARD_DARK, radius=S(6))
    bar_h = S(30)
    bar = (cam[0], cam[3] - bar_h, cam[2], cam[3])
    b.rect(bar, fill=GREEN, alpha=215)
    b.text(cam[0] + S(10), bar[1] + S(5), model.tracking_line, S(16), CREAM, False,
           max_w=left_w - S(20), container=bar)
    dy = bar[1] - S(6)
    for line in reversed(model.debug_lines):  # --debug-zones only; empty in finalist mode
        h = kit.height(S(15))
        dy -= h + 2
        b.rect((cam[0] + S(6), dy - 2, cam[0] + S(6) + min(left_w - S(12), int(kit.width(kit.txt(line), S(15))) + S(16)), dy + h + 2),
               fill=GREEN, alpha=215)
        b.text(cam[0] + S(12), dy, line, S(15), ORANGE, False, max_w=left_w - S(24), container=cam)

    ty = cam[3] + S(14)
    b.text(left_x, ty, "EVIDENCE TIMELINE", S(15), ORANGE, True, max_w=left_w // 2, container=(left_x, ty, left_x + left_w, ty + label_h + 4))
    if model.digital_event_count:
        pill_w = int(kit.width(model.sim_label, S(13), True)) + S(18)
        pr = (left_x + left_w - pill_w, ty - 1, left_x + left_w, ty + S(21))
        b.rect(pr, fill=ORANGE, radius=S(10))
        b.text(pr[0] + S(9), pr[1] + S(2), model.sim_label, S(13), GREEN, True, max_w=pill_w - S(10), container=pr)
    ty += label_h + S(8)
    row_h = S(27)
    cols = (S(10), S(112), S(236), S(478))
    if not model.timeline:
        b.text(left_x + S(10), ty, "No evidence yet. Enter Zone A to begin.", S(17), MUTED, False,
               max_w=left_w - S(20), container=(left_x, ty, left_x + left_w, content_bottom))
        out.left_bottom = ty + kit.height(S(17))
    else:
        last = len(model.timeline) - 1
        for i, e in enumerate(model.timeline):
            rr = (left_x, ty, left_x + left_w, ty + row_h - S(3))
            b.rect(rr, fill=CARD if i % 2 == 0 else mix(CARD, GREEN, 0.5), radius=S(4))
            bold = i == last
            ch_color = ORANGE if e.channel == "DIGITAL" else CREAM
            b.text(left_x + cols[0], ty + S(3), e.time_text, S(16), CREAM, bold, max_w=cols[1] - cols[0] - S(6), container=rr)
            b.text(left_x + cols[1], ty + S(3), e.channel, S(16), ch_color, True, max_w=cols[2] - cols[1] - S(6), container=rr)
            b.text(left_x + cols[2], ty + S(3), f"{e.step_id} {e.step_name}", S(16), CREAM, bold,
                   max_w=cols[3] - cols[2] - S(8), container=rr)
            b.text(left_x + cols[3], ty + S(3), e.detail, S(16), MUTED if e.channel == "PHYSICAL" else ORANGE, False,
                   max_w=left_w - cols[3] - S(10), container=rr)
            ty += row_h
        out.left_bottom = ty

    # ---- right column
    y = content_top
    # expected procedure
    y = section(right_x, y, right_w, "EXPECTED PROCEDURE")
    n = max(1, len(model.expected))
    arrow_gap = S(26)
    chip_w = (right_w - (n - 1) * arrow_gap) // n
    chip_h = S(54)
    for i, (sid, name) in enumerate(model.expected):
        cx = right_x + i * (chip_w + arrow_gap)
        cr = (cx, y, cx + chip_w, y + chip_h)
        b.rect(cr, fill=CARD, radius=S(8))
        b.text(cx + S(12), y + S(3), sid, S(22), ORANGE, True, max_w=chip_w - S(20), container=cr)
        b.text(cx + S(12), y + S(31), name, S(16), CREAM, False, max_w=chip_w - S(20), container=cr)
        if i < n - 1:
            b.text(cx + chip_w + arrow_gap // 2, y + S(14), "→", S(20), MUTED, False,
                   max_w=arrow_gap, container=(cx + chip_w, y, cx + chip_w + arrow_gap, y + chip_h), align="center")
    y += chip_h + gap

    def trace_card(title: str, parts: list[tuple[str, bool]], placeholder: str, count_text: str, sim_tag: bool) -> None:
        nonlocal y
        b.text(right_x, y, title, S(15), ORANGE, True, max_w=right_w // 2, container=(right_x, y, right_x + right_w, y + label_h + 4))
        if sim_tag:
            tw = int(kit.width(model.sim_label, S(13), True)) + S(20)
            pr = (right_x + right_w - tw, y - 1, right_x + right_w, y + S(21))
            b.rect(pr, fill=ORANGE, radius=S(10))
            b.text(pr[0] + S(10), pr[1] + S(2), model.sim_label, S(13), GREEN, True, max_w=tw - S(12), container=pr)
        y += label_h + S(4)
        ch = S(42)
        cr = (right_x, y, right_x + right_w, y + ch)
        b.rect(cr, fill=CARD, radius=S(8))
        if parts:
            text = " → ".join(f"{sid} (failed)" if failed else sid for sid, failed in parts)
            b.text(right_x + S(14), y + S(5), text, S(26), CREAM, True, max_w=right_w - S(150), container=cr)
        else:
            b.text(right_x + S(14), y + S(8), placeholder, S(20), MUTED, False, max_w=right_w - S(150), container=cr)
        b.text(right_x + right_w - S(14), y + S(12), count_text, S(15), MUTED, False, max_w=S(130), container=cr, align="right")
        y += ch + gap

    phys = [(sid, False) for sid in model.physical_trace]
    trace_card("PHYSICAL EVIDENCE", phys, "none yet", f"{len(phys)} observed", False)
    trace_card("DIGITAL EVIDENCE", model.digital_trace, "none yet", f"{len(model.digital_trace)} reported", True)

    # step states
    y = section(right_x, y, right_w, "STEP STATES")
    rh = S(32)
    for card in model.steps:
        rr = (right_x, y, right_x + right_w, y + rh)
        b.rect(rr, fill=CARD, radius=S(6))
        b.text(right_x + S(14), y + S(3), card.step_id, S(20), ORANGE, True, max_w=S(30), container=rr)
        b.text(right_x + S(48), y + S(4), card.name, S(19), CREAM, False, max_w=S(250), container=rr)
        bw = int(kit.width(card.indicator, S(14), True)) + S(22)
        bx = right_x + S(310)
        pr = (bx, y + S(4), bx + bw, y + rh - S(4))
        if card.indicator in ("MISSING", "CONFLICT"):
            b.rect(pr, fill=ORANGE, radius=S(11))
            tc = GREEN
        elif card.indicator == "OK":
            b.rect(pr, fill=CREAM, radius=S(11))
            tc = GREEN
        else:
            b.rect(pr, outline=CREAM if card.indicator == "UNCERTAIN" else MUTED, radius=S(11))
            tc = CREAM if card.indicator == "UNCERTAIN" else MUTED
        b.text(bx + S(11), pr[1] + S(2), card.indicator, S(14), tc, True, max_w=bw - S(12), container=pr)
        wx = right_x + S(310) + S(150) + S(14)
        b.text(wx, y + S(6), card.word, S(17), MUTED, False, max_w=right_x + right_w - wx - S(10), container=rr)
        y += rh + S(4)
    y += gap - S(4)

    # verdict (card height follows its content so nothing can overflow with taller fonts)
    y = section(right_x, y, right_w, "VERDICT")
    violated = model.verdict == "VIOLATED"
    h_status = kit.height(S(52), True)
    h_second = kit.height(S(27), True) if violated else kit.height(S(22))
    h_third = kit.height(S(18)) if violated else 0
    vh = max(S(128), S(8) + h_status + h_second + h_third + S(10))
    vr = (right_x, y, right_x + right_w, y + vh)
    if violated:
        fill, tc, outline = ORANGE, GREEN, None
    elif model.verdict == "COMPLETED":
        fill, tc, outline = CREAM, GREEN, None
    else:
        fill, tc, outline = CARD, CREAM, CREAM
    b.rect(vr, fill=fill, outline=outline, radius=S(12))
    sr = b.text(right_x + S(24), y + S(8), model.verdict, S(52), tc, True, max_w=right_w - S(48), container=vr)
    if violated:
        head = model.violation_labels[0] + (f"  +{model.extra_findings} more" if model.extra_findings else "")
        hr = b.text(right_x + S(24), sr[3], head, S(27), tc, True, max_w=right_w - S(48), container=vr)
        b.text(right_x + S(24), hr[3], f"Step {model.verdict_where}", S(18), tc, False, max_w=right_w - S(48), container=vr)
    else:
        sub = (labels.COMPLETED_TEXT if model.verdict == "COMPLETED"
               else labels.UNCERTAIN_TEXT if model.has_journey else labels.NO_JOURNEY_TEXT)
        b.text(right_x + S(24), sr[3] + S(2), sub, S(22), tc, False, max_w=right_w - S(48), container=vr)
    y += vh + gap

    # primary finding
    y = section(right_x, y, right_w, "PRIMARY FINDING")
    yy = b.wrap(right_x, y, model.primary_finding, S(22), right_w, 3, CREAM, False,
                container=(right_x, y, right_x + right_w, content_bottom))
    out.right_bottom = yy

    # ---- footer
    b.rect((m, footer_top, W - m, footer_top + 1), fill=MUTED)
    fy = footer_top + S(6)
    if notice:
        b.text(m, fy, notice, S(17), ORANGE, True, max_w=W - 2 * m, container=(0, footer_top, W, H))
    fy += S(26)
    b.text(m, fy, labels.CONTROLS_TEXT, S(15), CREAM, False, max_w=W - 2 * m, container=(0, footer_top, W, H))
    fy += S(24)
    b.text(m, fy, f"{labels.PRIVACY_FOOTER}   |   {labels.SIM_FOOTER}", S(15), MUTED, False,
           max_w=W - 2 * m, container=(0, footer_top, W, H))
    return out


# --------------------------------------------------------------------------- painter
def _fit_image(frame_rgb: Image.Image, box: Rect) -> tuple[Image.Image, Rect]:
    bw, bh = box[2] - box[0], box[3] - box[1]
    fw, fh = frame_rgb.size
    k = min(bw / fw, bh / fh)
    w, h = max(1, round(fw * k)), max(1, round(fh * k))
    x, y = box[0] + (bw - w) // 2, box[1] + (bh - h) // 2
    return frame_rgb.resize((w, h), Image.BILINEAR), (x, y, x + w, y + h)


def paint(layout: Layout, kit: FontKit, frame_bgr: Any = None, zones: ZoneSet | None = None,
          persons: list[PersonView] | None = None, debug: bool = False) -> Image.Image:
    """Render the dashboard to an RGB PIL image of exactly layout.width x layout.height."""
    W, H, s = layout.width, layout.height, layout.scale
    img = Image.new("RGB", (W, H), GREEN)
    draw = ImageDraw.Draw(img)

    # 1) static cards, then camera + overlays, then all text (so the camera bars/labels sit on top)
    cam_box = layout.camera_box
    camera_rects = [o for o in layout.ops if o.kind == "rect" and o.alpha < 255]
    solid_rects = [o for o in layout.ops if o.kind == "rect" and o.alpha == 255]
    for op in solid_rects:
        kw = {}
        if op.fill is not None:
            kw["fill"] = op.fill
        if op.outline is not None:
            kw["outline"] = op.outline
            kw["width"] = max(2, round(2 * s))
        (draw.rounded_rectangle(op.rect, radius=op.radius, **kw) if op.radius else draw.rectangle(op.rect, **kw))
    if frame_bgr is not None:
        rgb = Image.fromarray(frame_bgr[:, :, ::-1])
        cam_img, ir = _fit_image(rgb, cam_box)
        cam_img = _camera_overlays(cam_img, kit, s, zones, persons or [], debug)
        img.paste(cam_img, (ir[0], ir[1]))
    for op in camera_rects:  # translucent bars over the camera (blend only the bar's own pixels)
        x0, y0, x1, y1 = (max(0, op.rect[0]), max(0, op.rect[1]), min(W, op.rect[2]), min(H, op.rect[3]))
        if x1 > x0 and y1 > y0:
            region = img.crop((x0, y0, x1, y1))
            img.paste(Image.blend(region, Image.new("RGB", region.size, op.fill), op.alpha / 255), (x0, y0))
    draw = ImageDraw.Draw(img)
    for op in layout.texts():
        draw.text((op.rect[0], op.rect[1]), op.text, font=kit.font(op.size, op.bold), fill=op.color)
    return img


def _camera_overlays(cam: Image.Image, kit: FontKit, s: float, zones: ZoneSet | None,
                     persons: list[PersonView], debug: bool) -> Image.Image:
    w, h = cam.size
    ov = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    active = {p.zone_id for p in persons if p.zone_id}
    lw = max(2, round(2 * s))
    if zones is not None:
        for z in zones:
            x1, y1, x2, y2 = round(z.x1 * w), round(z.y1 * h), round(z.x2 * w), round(z.y2 * h)
            on = z.zone_id in active
            d.rectangle((x1, y1, x2, y2), fill=(*(ORANGE if on else CREAM), 70 if on else 26),
                        outline=(*(ORANGE if on else CREAM), 255), width=lw + (1 if on else 0))
            name = kit.txt(labels.humanize(z.name))
            size = max(11, round(13 * s))
            while kit.width(name, size) > (x2 - x1 - 10) and size > 10:
                size -= 1
            tag_w = max(int(kit.width(name, size)) + 10, int(kit.width(z.zone_id, round(17 * s), True)) + 10)
            d.rectangle((x1 + 3, y1 + 3, x1 + 3 + min(tag_w, x2 - x1 - 6), y1 + 3 + round(20 * s) + kit.height(size) + 2),
                        fill=(*GREEN, 215))
            d.text((x1 + 8, y1 + 4), z.zone_id, font=kit.font(max(12, round(17 * s)), True), fill=(*ORANGE, 255))
            d.text((x1 + 8, y1 + 4 + round(20 * s)), name, font=kit.font(size), fill=(*CREAM, 255))
    for p in persons:
        x1, y1, x2, y2 = round(p.box[0] * w), round(p.box[1] * h), round(p.box[2] * w), round(p.box[3] * h)
        col = ORANGE if p.journey_id else CREAM
        d.rectangle((x1, y1, x2, y2), outline=(*col, 255), width=lw + 1)
        tag = kit.txt(f"ID {p.tracker_id} · {p.confidence:.2f}")
        size = max(11, round(13 * s))
        tw, th = int(kit.width(tag, size)) + 10, kit.height(size) + 4
        ty = y1 - th if y1 - th > 0 else y1
        d.rectangle((x1, ty, x1 + tw, ty + th), fill=(*GREEN, 230))
        d.text((x1 + 5, ty + 2), tag, font=kit.font(size), fill=(*col, 255))
        if debug and p.debug is not None:
            cx, cy = round(p.debug.smoothed_point[0] * w), min(h - 1, round(p.debug.smoothed_point[1] * h))
            d.line((cx - 8, cy, cx + 8, cy), fill=(*CREAM, 255), width=2)
            d.line((cx, cy - 8, cx, cy + 8), fill=(*CREAM, 255), width=2)
    return Image.alpha_composite(cam.convert("RGBA"), ov).convert("RGB")


def to_bgr(img: Image.Image) -> Any:
    import numpy as np
    return np.ascontiguousarray(np.asarray(img)[:, :, ::-1])
