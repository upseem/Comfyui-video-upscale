"""Build the disk-backed native SeedVR2 workflow from checked-in templates.

Run from the repository root. The official native template snapshot is checked in
only as the resulting subgraph inside the generated workflow; pass a current
official workflow to refresh that subgraph deliberately.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "example_workflows/SeedVR2_5090_disk_batch_1080p.json"
OUT = ROOT / "example_workflows/SeedVR2_3B_Int8_Video_Upscale_5090.json"


def reset(node: dict, node_id: int, pos: list[int]) -> dict:
    node = copy.deepcopy(node)
    node["id"] = node_id
    node["pos"] = pos
    node["order"] = node_id - 1
    for item in node.get("inputs", []):
        item["link"] = None
    for item in node.get("outputs", []):
        item["links"] = None
    return node


def connect(nodes: list[dict], links: list[list], src: int, out_slot: int, dst: int, input_name: str) -> None:
    a = next(n for n in nodes if n["id"] == src)
    b = next(n for n in nodes if n["id"] == dst)
    in_slot = next(i for i, item in enumerate(b["inputs"]) if item["name"] == input_name)
    link_id = len(links) + 1
    data_type = a["outputs"][out_slot]["type"]
    links.append([link_id, src, out_slot, dst, in_slot, data_type])
    a["outputs"][out_slot]["links"] = (a["outputs"][out_slot]["links"] or []) + [link_id]
    b["inputs"][in_slot]["link"] = link_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("official", type=Path, help="Official SeedVR2 3B Int8 UI workflow JSON")
    args = parser.parse_args()
    base = json.loads(BASE.read_text())
    official = json.loads(args.official.read_text())
    old = {n["id"]: n for n in base["nodes"]}
    official_subgraph_node = next(n for n in official["nodes"] if n["type"] == official["definitions"]["subgraphs"][0]["id"])
    short = json.loads((ROOT / "example_workflows/SeedVR2_5090_short_clip_1080p.json").read_text())
    create_template = next(n for n in short["nodes"] if n["type"] == "CreateVideo")
    components_template = next(n for n in short["nodes"] if n["type"] == "GetVideoComponents")

    prepare = reset(old[1], 1, [0, 80])
    prepare["widgets_values"] = ["input.mp4", 0, 0, 0, "seedvr2_native_full_video", "image"]
    plan = reset(old[2], 2, [370, 80])
    plan["widgets_values"] = [49, 8]
    start = reset(old[3], 3, [740, 80])
    read = reset(old[4], 4, [1100, 80])
    create = reset(create_template, 5, [1450, 80])
    create["widgets_values"] = [30]
    native = reset(official_subgraph_node, 6, [1800, 80])
    components = reset(components_template, 7, [2290, 80])
    write = reset(old[8], 8, [2590, 80])
    write["widgets_values"] = ["overwrite"]
    end = reset(old[9], 9, [2940, 80])
    assemble = reset(old[10], 10, [3290, 80])
    assemble["widgets_values"] = [18, "medium", "aac", False]
    nodes = [prepare, plan, start, read, create, native, components, write, end, assemble]
    links: list[list] = []
    for edge in [
        (1, 1, 2, "frame_count"), (2, 0, 3, "mode.max_iteration"),
        (1, 0, 4, "job_directory"), (3, 0, 4, "chunk_index"),
        (2, 1, 4, "chunk_size"), (2, 2, 4, "context"),
        (4, 0, 5, "images"), (1, 2, 5, "fps"),
        (5, 0, 6, "video"), (6, 0, 7, "video"),
        (1, 0, 8, "job_directory"), (4, 1, 8, "batch_receipt"),
        (7, 0, 8, "images"), (8, 0, 9, "output_value"),
        (8, 0, 9, "terminations.termination0"),
        (1, 0, 10, "job_directory"), (9, 0, 10, "completion_barrier"),
    ]:
        connect(nodes, links, *edge)
    result = {
        "id": "seedvr2-native-disk-batch-5090",
        "revision": 0,
        "last_node_id": 10,
        "last_link_id": len(links),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "definitions": copy.deepcopy(official["definitions"]),
        "config": {},
        "extra": {"info": "Disk-backed full-video native SeedVR2 3B Int8; outer chunks 49 + context 8"},
        "version": 0.4,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
