import json
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / "example_workflows/SeedVR2_3B_Int8_native_disk_batch_5090.json"


def load():
    return json.loads(WORKFLOW.read_text())


def test_links_are_consistent():
    data = load()
    nodes = {node["id"]: node for node in data["nodes"]}
    for link_id, src, out_slot, dst, in_slot, _ in data["links"]:
        assert link_id in nodes[src]["outputs"][out_slot]["links"]
        assert nodes[dst]["inputs"][in_slot]["link"] == link_id


def test_native_seedvr_and_disk_chunking_are_composed():
    data = load()
    types = [node["type"] for node in data["nodes"]]
    graph = data["definitions"]["subgraphs"][0]
    native_types = [node["type"] for node in graph["nodes"]]
    assert {"VideoUpscaleBatchPlan", "VideoUpscaleReadBatch", "VideoUpscaleWriteBatch"} <= set(types)
    assert "SeedVR2VideoUpscaler" not in types  # third-party all-in-memory node
    assert {"SeedVR2TemporalChunk", "SeedVR2TemporalMerge", "SeedVR2Conditioning"} <= set(native_types)


def test_safe_full_video_defaults():
    data = load()
    prepare = next(node for node in data["nodes"] if node["type"] == "VideoLoopPrepare")
    plan = next(node for node in data["nodes"] if node["type"] == "VideoUpscaleBatchPlan")
    assert prepare["widgets_values"][1:4] == [0, 0, 0]  # source FPS, start, full duration
    assert plan["widgets_values"] == [49, 8]
    graph = data["definitions"]["subgraphs"][0]
    by_id = {node["id"]: node for node in graph["nodes"]}
    assert by_id[81]["widgets_values"] == [False]  # no inner trim
    assert by_id[105]["widgets_values"] == [True]  # latent splitting still enabled
    assert by_id[99]["widgets_values"] == [2, "auto"]
    assert by_id[52]["widgets_values"][0] == "seedvr2_3b_int8_convrot.safetensors"
    assert by_id[51]["widgets_values"][0] == "seedvr2_ema_vae_fp16.safetensors"
    assert by_id[59]["widgets_values"] == ["lab"]
