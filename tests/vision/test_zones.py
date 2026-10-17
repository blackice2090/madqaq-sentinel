import json

import pytest

from sentinel.vision.config import ZoneConfigError
from sentinel.vision.zones import Zone, ZoneSet, center_point, ground_point, normalize_box, to_pixels

REPO_ZONES = "config/checkpoint_zones.json"


@pytest.fixture
def zones():
    return ZoneSet.load(REPO_ZONES)


# 1. point inside / outside each zone
@pytest.mark.parametrize("zone_id, inside, outside", [
    ("A", (0.13, 0.5), (0.25, 0.5)),
    ("B", (0.38, 0.5), (0.26, 0.5)),
    ("C", (0.63, 0.5), (0.75, 0.5)),
    ("D", (0.87, 0.5), (0.99, 0.5)),
])
def test_point_inside_and_outside_each_zone(zones, zone_id, inside, outside):
    z = zones.get(zone_id)
    assert z.contains(inside)
    assert not z.contains(outside)
    assert zones.locate(inside).zone_id == zone_id
    assert zones.locate(outside) is None


def test_point_above_zone_is_outside(zones):
    assert zones.locate((0.13, 0.02)) is None


def test_edges_are_inclusive():
    z = Zone("A", "Entry", 0.1, 0.1, 0.2, 0.2)
    assert z.contains((0.1, 0.1)) and z.contains((0.2, 0.2))


# 2. normalized coordinate conversion
def test_normalize_box_converts_pixels_to_unit_range():
    assert normalize_box((64, 48, 320, 480), 640, 480) == (0.1, 0.1, 0.5, 1.0)


def test_normalize_box_clamps_and_orders():
    assert normalize_box((700, -10, 600, 500), 640, 480) == (600 / 640, 0.0, 1.0, 1.0)


def test_normalize_box_is_resolution_independent():
    assert normalize_box((64, 48, 320, 240), 640, 480) == normalize_box((128, 96, 640, 480), 1280, 960)


def test_normalize_box_rejects_bad_frame_size():
    with pytest.raises(ValueError):
        normalize_box((0, 0, 1, 1), 0, 480)


def test_ground_point_is_bottom_center():
    assert ground_point((0.2, 0.1, 0.4, 0.9)) == (pytest.approx(0.3), 0.9)
    assert center_point((0.2, 0.1, 0.4, 0.9)) == (pytest.approx(0.3), pytest.approx(0.5))


def test_to_pixels_round_trip():
    assert to_pixels((0.1, 0.1, 0.5, 1.0), 640, 480) == (64, 48, 320, 480)


# zone config behaviour
def test_shipped_config_defines_a_to_d_in_order(zones):
    assert zones.ids == ["A", "B", "C", "D"]
    assert [z.name for z in zones] == ["Entry", "Credential Check", "Screening", "Exit"]


def test_missing_config_file(tmp_path):
    with pytest.raises(ZoneConfigError, match="not found"):
        ZoneSet.load(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    p = tmp_path / "z.json"
    p.write_text("{not json")
    with pytest.raises(ZoneConfigError, match="not valid JSON"):
        ZoneSet.load(p)


@pytest.mark.parametrize("spec, msg", [
    ({"name": "X", "x1": 0.5, "y1": 0.0, "x2": 0.2, "y2": 1.0}, "x1 < x2"),
    ({"name": "X", "x1": -0.1, "y1": 0.0, "x2": 0.2, "y2": 1.0}, "outside"),
    ({"name": "X", "x1": 0.0, "y1": 0.0, "x2": 1.5, "y2": 1.0}, "outside"),
    ({"name": "X", "x1": "a", "y1": 0.0, "x2": 0.2, "y2": 1.0}, "finite number"),
    ({"name": "X", "x1": 0.0, "y1": 0.0, "x2": 0.2}, "y2"),
    ({"x1": 0.0, "y1": 0.0, "x2": 0.2, "y2": 1.0}, "name"),
])
def test_malformed_zone_coordinates(tmp_path, spec, msg):
    p = tmp_path / "z.json"
    p.write_text(json.dumps({"A": spec}))
    with pytest.raises(ZoneConfigError, match=msg):
        ZoneSet.load(p)


def test_overlapping_zones_rejected():
    data = {
        "A": {"name": "a", "x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0},
        "B": {"name": "b", "x1": 0.4, "y1": 0.0, "x2": 0.9, "y2": 1.0},
    }
    with pytest.raises(ZoneConfigError, match="overlap"):
        ZoneSet.from_dict(data)


def test_non_object_config_rejected():
    with pytest.raises(ZoneConfigError):
        ZoneSet.from_dict([1, 2])
