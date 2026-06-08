from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = MODULE_ROOT / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

from iso216_guidecut import compute_expand_crop_rect, compute_grid, compute_guides, detect_orientation


FIXTURE_PATH = MODULE_ROOT.parent / "guidecut-webapp" / "fixtures" / "geometry.json"


@pytest.fixture(scope="module")
def geometry_fixtures() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_web_orientation_fixtures_match_python(geometry_fixtures: dict) -> None:
    for case in geometry_fixtures["orientations"]:
        assert detect_orientation(case["width"], case["height"]) == case["expected"]


def test_web_preset_grid_fixtures_match_python(geometry_fixtures: dict) -> None:
    for case in geometry_fixtures["presetGrids"]:
        assert compute_grid(case["target"].lower(), case["orientation"]) == (
            case["cols"],
            case["rows"],
        )


def test_web_guide_fixture_matches_python(geometry_fixtures: dict) -> None:
    case = geometry_fixtures["guides"]
    vertical, horizontal = compute_guides(
        case["width"],
        case["height"],
        case["cols"],
        case["rows"],
    )
    assert vertical == case["vertical"]
    assert horizontal == case["horizontal"]


def test_web_crop_fixtures_match_python(geometry_fixtures: dict) -> None:
    for case in geometry_fixtures["cropCases"]:
        crop = compute_expand_crop_rect(case["width"], case["height"], case["bias"])
        assert crop.axis == case["axis"]
        if "leading" in case:
            assert crop.leading_trim_px == case["leading"]
        if "trailing" in case:
            assert crop.trailing_trim_px == case["trailing"]
        if "excess" in case:
            assert crop.excess_px == case["excess"]
