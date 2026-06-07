from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eyebrain.index import MomentIndex  # noqa: E402
from eyebrain.models import Moment  # noqa: E402


def build_demo_moments() -> list[Moment]:
    return [
        Moment(
            camera_id="front_display",
            camera_name="Front Counter Display",
            start_sec=610,
            end_sec=620,
            summary="The countertop display is upright while two customers stand near the counter.",
            tags=["display", "counter", "normal"],
            confidence=0.92,
        ),
        Moment(
            camera_id="front_display",
            camera_name="Front Counter Display",
            start_sec=638,
            end_sec=646,
            summary="A backpack clips the countertop display and knocks it over onto the floor.",
            tags=["display", "knocked over", "incident", "backpack"],
            confidence=0.95,
        ),
        Moment(
            camera_id="front_display",
            camera_name="Front Counter Display",
            start_sec=655,
            end_sec=670,
            summary="A staff member picks up the fallen display and places it back on the counter.",
            tags=["display", "recovered", "staff"],
            confidence=0.88,
        ),
        Moment(
            camera_id="north_hall",
            camera_name="North Hallway",
            start_sec=122,
            end_sec=136,
            summary="A contractor carries a yellow toolbox and a coiled extension cord through the side door.",
            tags=["contractor", "toolbox", "equipment"],
            confidence=0.91,
        ),
        Moment(
            camera_id="north_hall",
            camera_name="North Hallway",
            start_sec=185,
            end_sec=205,
            summary="The contractor leaves the yellow toolbox and extension cord beside the north hallway equipment rack.",
            tags=["contractor", "equipment", "left behind", "north hallway"],
            confidence=0.96,
        ),
        Moment(
            camera_id="north_hall",
            camera_name="North Hallway",
            start_sec=420,
            end_sec=442,
            summary="The contractor exits through the side door without the toolbox; the equipment remains by the rack.",
            tags=["contractor", "equipment remains", "confirmation"],
            confidence=0.9,
        ),
        Moment(
            camera_id="dining_room",
            camera_name="Dining Room",
            start_sec=900,
            end_sec=930,
            summary="Table 12 has been seated and menus are closed, but no food has arrived.",
            tags=["table 12", "waiting", "order"],
            confidence=0.9,
        ),
        Moment(
            camera_id="dining_room",
            camera_name="Dining Room",
            start_sec=1140,
            end_sec=1170,
            summary="Table 12 is still waiting on their order after about four minutes with no plates on the table.",
            tags=["table 12", "waiting", "order delay"],
            confidence=0.93,
        ),
        Moment(
            camera_id="dining_room",
            camera_name="Dining Room",
            start_sec=1320,
            end_sec=1350,
            summary="A server delivers food to table 12 after roughly seven minutes of waiting.",
            tags=["table 12", "food delivered", "order"],
            confidence=0.94,
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a local eyebrain demo index.")
    parser.add_argument("--index-dir", default="data/index", help="Index directory to write.")
    parser.add_argument("--reset", action="store_true", help="Clear existing index first.")
    args = parser.parse_args()

    index = MomentIndex(args.index_dir)
    if args.reset:
        index.clear()
    indexed = index.add_moments(build_demo_moments())
    print(f"Indexed {len(indexed)} demo moments into {index.path}")


if __name__ == "__main__":
    main()
