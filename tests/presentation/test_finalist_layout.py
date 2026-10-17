"""Finalist dashboard: layout/clipping/disclosure tests. Needs Pillow (part of the vision extra); skipped otherwise."""
import json
from itertools import combinations

import pytest

pytest.importorskip("PIL")

from apps.finalist_demo.fonts import FontKit  # noqa: E402
from apps.finalist_demo.render import GREEN, layout_dashboard, paint  # noqa: E402
from sentinel.digital import B_FAILED, FULL_TRACE, WITHOUT_B  # noqa: E402
from sentinel.presentation import build_dashboard_model, labels, save_snapshot  # noqa: E402
from sentinel.vision.event_emitter import TrackerDebug  # noqa: E402
from sentinel.vision.pipeline import PersonView  # noqa: E402
from sentinel.vision.zones import ZoneSet  # noqa: E402

SIZES = [(1920, 1080), (1600, 900)]
SCENARIOS = {
    "none": (None, None),
    "completed": ("ABCD", FULL_TRACE),
    "phantom": ("ACD", FULL_TRACE),
    "omission": ("ACD", WITHOUT_B),
    "contradiction": ("ABCD", B_FAILED),
    "physical_only": ("ABCD", None),
    "inversion": ("ACB", None),
}
DEBUG_WORDS = ("Raw zone", "Candidate zone", "Dwell", "Stable zone", "Smoothed ground")


@pytest.fixture(scope="module")
def kit():
    return FontKit()


def build(coordinator, walk, name, **kw):
    physical, preset = SCENARIOS[name]
    if physical:
        coordinator.add_physical_events(walk(physical))
    if preset:
        coordinator.inject_digital_preset(preset)
    return build_dashboard_model(coordinator, **kw)


def inside(inner, outer, tol=0):
    return inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol


def overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def assert_layout_clean(layout):
    W, H = layout.width, layout.height
    texts = layout.texts()
    assert texts
    for op in texts:
        assert inside(op.rect, (0, 0, W, H)), f"off canvas: {op.text!r} {op.rect}"
        if op.container is not None:
            assert inside(op.rect, op.container, tol=1), f"clipped by container: {op.text!r} {op.rect} vs {op.container}"
    for a, b in combinations(texts, 2):
        assert not overlap(a.rect, b.rect), f"text overlap: {a.text!r} {a.rect} / {b.text!r} {b.rect}"
    assert layout.right_bottom <= layout.footer_top, f"right column runs into footer ({layout.right_bottom} > {layout.footer_top})"
    assert layout.left_bottom <= layout.footer_top, f"timeline runs into footer ({layout.left_bottom} > {layout.footer_top})"
    cam = layout.camera_box
    assert cam[2] <= W and cam[3] <= layout.footer_top


# 16. no clipping at the target render sizes
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_no_clipping_or_overlap(coordinator, walk, kit, size, name):
    m = build(coordinator, walk, name)
    assert_layout_clean(layout_dashboard(m, *size, kit))


@pytest.mark.parametrize("size", SIZES)
def test_no_clipping_with_long_notice_and_debug_lines(coordinator, walk, kit, size):
    m = build(coordinator, walk, "phantom")
    dbg = TrackerDebug("B", "C", "B", 240.0, 600.0, (0.4, 0.9), (0.41, 0.95))
    person = PersonView(12, 0.91, (0.3, 0.2, 0.5, 0.95), "B", coordinator.active_journey_id, dbg)
    m = build_dashboard_model(coordinator, [person], debug=True)
    assert_layout_clean(layout_dashboard(m, *size, kit, notice="Digital evidence is already present for this journey. Press 0 to clear it first, or R to reset. " * 2))


def test_text_is_fitted_even_with_a_wide_fallback_font(coordinator, walk):
    """Shrink/ellipsize protects against clipping whatever font the machine has (here: Pillow's built-in)."""
    fallback = FontKit(regular=["nonexistent.ttf"], bold=["nonexistent.ttf"])
    m = build(coordinator, walk, "phantom")
    layout = layout_dashboard(m, 1600, 900, fallback)
    assert_layout_clean(layout)
    assert "→" not in layout.all_text() and "•" not in layout.all_text()  # transliterated, never tofu boxes


# 13. no raw underscores on screen
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_rendered_text_has_no_raw_underscores(coordinator, walk, kit, name):
    layout = layout_dashboard(build(coordinator, walk, name), 1600, 900, kit)
    assert "_" not in layout.all_text(), [o.text for o in layout.texts() if "_" in o.text]


# 14. simulator disclosure
@pytest.mark.parametrize("name", [n for n in SCENARIOS if SCENARIOS[n][1] is not None])
def test_simulated_label_visible_when_digital_evidence_exists(coordinator, walk, kit, name):
    text = layout_dashboard(build(coordinator, walk, name), 1600, 900, kit).all_text()
    assert text.count(labels.SIM_LABEL) >= 2  # digital evidence section + timeline
    assert labels.SIM_FOOTER in text


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_simulated_label_is_always_on_screen(coordinator, walk, kit, name):
    text = layout_dashboard(build(coordinator, walk, name), 1600, 900, kit).all_text()
    assert labels.SIM_LABEL in text and labels.SIM_FOOTER in text


# 15. privacy disclosure
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_privacy_disclosure_present(coordinator, walk, kit, name):
    assert kit.txt(labels.PRIVACY_FOOTER) in layout_dashboard(build(coordinator, walk, name), 1600, 900, kit).all_text()


def test_controls_footer_lists_all_keys(coordinator, walk, kit):
    text = layout_dashboard(build(coordinator, walk, "none"), 1600, 900, kit).all_text()
    for token in ("1 Digital full trace", "2 Digital without B", "3 Digital B failed", "0 Clear digital", "S Save evidence", "R Reset", "Q Quit"):
        assert token in text


# 11 / 12 at the rendered level
def test_finalist_mode_renders_no_debug_text(coordinator, walk, kit):
    dbg = TrackerDebug("B", "C", "B", 240.0, 600.0, (0.4, 0.9), (0.41, 0.95))
    walk_events = build(coordinator, walk, "phantom")  # noqa: F841
    person = PersonView(3, 0.9, (0.3, 0.2, 0.5, 0.95), "B", coordinator.active_journey_id, dbg)
    text = layout_dashboard(build_dashboard_model(coordinator, [person], debug=False), 1600, 900, kit).all_text()
    assert not any(w in text for w in DEBUG_WORDS)
    assert "Tracking ID 3" in text  # small tracker id / zone / confidence is allowed


def test_debug_mode_renders_diagnostics(coordinator, walk, kit):
    build(coordinator, walk, "phantom")
    dbg = TrackerDebug("B", "C", "B", 240.0, 600.0, (0.4, 0.9), (0.41, 0.95))
    person = PersonView(3, 0.9, (0.3, 0.2, 0.5, 0.95), "B", coordinator.active_journey_id, dbg)
    text = layout_dashboard(build_dashboard_model(coordinator, [person], debug=True), 1600, 900, kit).all_text()
    assert all(w in text for w in DEBUG_WORDS)


# hierarchy / content
def test_dashboard_sections_and_verdict_wording(coordinator, walk, kit):
    text = layout_dashboard(build(coordinator, walk, "phantom"), 1600, 900, kit).all_text()
    for token in ("MADQAQ Sentinel", "Procedure Integrity Monitor", "LIVE CAMERA / PHYSICAL CHANNEL", "EXPECTED PROCEDURE",
                  "PHYSICAL EVIDENCE", "DIGITAL EVIDENCE", "STEP STATES", "VERDICT", "PRIMARY FINDING", "EVIDENCE TIMELINE",
                  "VIOLATED", "PHANTOM COMPLETION", "Credential Check was recorded digitally"):
        assert token in text, token
    assert "PHANTOM_COMPLETION" not in text


def test_timeline_rows_are_real_events(coordinator, walk, kit):
    m = build(coordinator, walk, "completed")
    layout = layout_dashboard(m, 1600, 900, kit)
    shown = [o.text for o in layout.texts()]
    assert sum(t in ("PHYSICAL", "DIGITAL") for t in shown) == len(m.timeline) == 8
    empty = layout_dashboard(build_dashboard_model(coordinator.__class__(coordinator.procedure)), 1600, 900, kit).all_text()
    assert "PHYSICAL\n" not in empty and "No evidence yet" in empty


# painter + snapshot end-to-end
def test_paint_renders_exact_size_with_project_colours(coordinator, walk, kit):
    np = pytest.importorskip("numpy")
    m = build(coordinator, walk, "phantom")
    zones = ZoneSet.load("config/checkpoint_zones.json")
    frame = np.full((480, 640, 3), 80, np.uint8)
    for size in SIZES:
        img = paint(layout_dashboard(m, *size, kit), kit, frame, zones, [], False)
        assert img.size == size
        assert img.getpixel((size[0] - 2, size[1] // 2)) == GREEN  # deep-green background
    orange = (217, 120, 74)
    assert int((np.asarray(img) == np.array(orange, dtype=np.uint8)).all(axis=2).sum()) > 20000  # violated verdict card is orange


def test_paint_without_camera_frame_still_renders(coordinator, walk, kit):
    img = paint(layout_dashboard(build(coordinator, walk, "none"), 1600, 900, kit), kit)
    assert img.size == (1600, 900)


def test_snapshot_end_to_end_png_and_json(coordinator, walk, kit, tmp_path):
    from datetime import datetime, timedelta, timezone

    import PIL.Image as PILImage
    np = pytest.importorskip("numpy")
    m = build(coordinator, walk, "phantom")
    img = paint(layout_dashboard(m, 1600, 900, kit), kit, np.full((480, 640, 3), 80, np.uint8),
                ZoneSet.load("config/checkpoint_zones.json"), [], False)
    now = datetime(2026, 10, 17, 17, 20, 15, tzinfo=timezone(timedelta(hours=3)))
    paths = save_snapshot(coordinator, lambda p: (img.save(p), True)[1], tmp_path / "artifacts" / "evidence", now)
    assert paths.png.name == "2026-10-17_172015_PHANTOM_COMPLETION.png"
    assert PILImage.open(paths.png).size == (1600, 900)
    data = json.loads(paths.json.read_text(encoding="utf-8"))
    assert data["digital_simulated"] is True and data["verdict"] == "VIOLATED"
    assert data["violation_types"] == ["PHANTOM_COMPLETION"]
    assert data["image_file"] == paths.png.name
