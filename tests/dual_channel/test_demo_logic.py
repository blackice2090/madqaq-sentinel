"""Demo glue that needs neither a camera nor a model (key handling, panel layout)."""
import pytest

from apps.dual_channel_demo.main import handle_key
from sentinel.digital import B_FAILED, FULL_TRACE, WITHOUT_B
from sentinel.dual_channel.coordinator import NO_JOURNEY_MESSAGE
from sentinel.vision.config import VisionConfig
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.zones import ZoneSet


@pytest.fixture
def pipeline(procedure):
    zones = ZoneSet.load("config/checkpoint_zones.json")
    return PerceptionPipeline(zones, PhysicalEventEmitter(zones, procedure.procedure_id, VisionConfig()), procedure)


def test_digital_key_without_journey_shows_message_and_creates_nothing(coordinator, pipeline):
    for key in (ord("1"), ord("2"), ord("3"), ord("0")):
        assert handle_key(key, coordinator, pipeline) == NO_JOURNEY_MESSAGE
    assert coordinator.journey_ids == []


def test_key_1_injects_once_only(coordinator, pipeline, walk):
    coordinator.add_physical_events(walk("ABCD"))
    assert "SIMULATED" in handle_key(ord("1"), coordinator, pipeline)
    first = coordinator.digital_events()
    assert "already present" in handle_key(ord("1"), coordinator, pipeline)
    assert "already present" in handle_key(ord("2"), coordinator, pipeline)
    assert coordinator.digital_events() == first


def test_key_0_clears_and_allows_new_preset(coordinator, pipeline, walk):
    coordinator.add_physical_events(walk("ABCD"))
    handle_key(ord("1"), coordinator, pipeline)
    assert "cleared" in handle_key(ord("0"), coordinator, pipeline)
    assert coordinator.digital_events() == []
    handle_key(ord("3"), coordinator, pipeline)
    assert [e.event_type.value for e in coordinator.digital_events()][1] == "STEP_FAILED"


def test_key_r_resets_physical_digital_and_coordinator(coordinator, pipeline, walk):
    events = walk("ABCD")
    pipeline.emitter.process([], events[0].timestamp)  # touch pipeline; real events were produced by another emitter
    coordinator.add_physical_events(events)
    handle_key(ord("1"), coordinator, pipeline)
    assert "Reset" in handle_key(ord("R"), coordinator, pipeline)
    assert coordinator.journey_ids == [] and coordinator.active_journey_id is None
    assert pipeline.emitter.journeys == {}


def test_unmapped_key_is_ignored(coordinator, pipeline):
    assert handle_key(ord("x"), coordinator, pipeline) is None
    assert handle_key(255, coordinator, pipeline) is None


# ---- panel rendering (needs opencv + numpy; skipped when the vision extra is absent) ----
@pytest.mark.parametrize("physical, preset", [
    ("ABCD", None), ("ABCD", FULL_TRACE), ("ACD", FULL_TRACE), ("ACD", WITHOUT_B), ("ABCD", B_FAILED), ("ACD", None),
])
def test_panel_renders_and_content_fits(coordinator, walk, physical, preset):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from apps.dual_channel_demo.overlay import MIN_HEIGHT, PANEL_W, draw_dual_panel
    coordinator.add_physical_events(walk(physical))
    if preset:
        coordinator.inject_digital_preset(preset)
    panel, last_y = draw_dual_panel(cv2, np, 480, coordinator.summary(), "x" * 90)
    assert panel.shape == (MIN_HEIGHT, PANEL_W, 3)
    footer_top = MIN_HEIGHT - 14 - 2 * 18 - 8 - 2 * 18  # controls + a 2-line notice
    assert last_y <= footer_top, f"content ends at y={last_y}, footer starts at {footer_top}"


def test_panel_without_journey_renders():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from apps.dual_channel_demo.overlay import draw_dual_panel
    panel, _ = draw_dual_panel(cv2, np, 480, None, "")
    assert panel.shape[0] >= 540


def test_simulated_label_is_always_drawn():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from apps.dual_channel_demo import overlay
    assert "SIMULATED" in overlay.SIM_BANNER and "not a real" in overlay.SIM_NOTE
    # the orange banner is painted with the project orange in both the no-journey and journey states
    panel, _ = overlay.draw_dual_panel(cv2, np, 480, None, "")
    assert (panel == np.array(overlay.ORANGE, dtype=np.uint8)).all(axis=2).sum() > 5000
