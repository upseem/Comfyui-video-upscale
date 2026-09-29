import json
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / "example_workflows/SeedVR2_3B_Int8_Video_Upscale_5090.json"


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


def test_6000_profile_uses_measured_safe_batch_and_fast_png():
    path = WORKFLOW.with_name("SeedVR2_3B_Int8_Video_Upscale_6000_96GB.json")
    data = json.loads(path.read_text())
    plan = next(node for node in data["nodes"] if node["type"] == "VideoUpscaleBatchPlan")
    writer = next(node for node in data["nodes"] if node["type"] == "VideoUpscaleWriteBatch")
    assert plan["widgets_values"] == [57, 4]
    assert writer["widgets_values"] == ["overwrite", 0]
    assert any(item["name"] == "png_compress_level" for item in writer["inputs"])


def test_6000_7b_fp16_profile_only_changes_model_variant():
    base_path = WORKFLOW.with_name("SeedVR2_3B_Int8_Video_Upscale_6000_96GB.json")
    fp16_path = WORKFLOW.with_name("SeedVR2_7B_FP16_Video_Upscale_6000_96GB.json")
    base = json.loads(base_path.read_text())
    fp16 = json.loads(fp16_path.read_text())
    base_graph = base["definitions"]["subgraphs"][0]
    fp16_graph = fp16["definitions"]["subgraphs"][0]
    base_unet = next(n for n in base_graph["nodes"] if n["type"] == "UNETLoader")
    fp16_unet = next(n for n in fp16_graph["nodes"] if n["type"] == "UNETLoader")
    assert base_unet["widgets_values"][0] == "seedvr2_3b_int8_convrot.safetensors"
    assert fp16_unet["widgets_values"][0] == "seedvr2_7b_fp16.safetensors"
    assert next(n for n in fp16_graph["nodes"] if n["type"] == "VAELoader")["widgets_values"][0] == "seedvr2_ema_vae_fp16.safetensors"
    for data in (base, fp16):
        plan = next(n for n in data["nodes"] if n["type"] == "VideoUpscaleBatchPlan")
        writer = next(n for n in data["nodes"] if n["type"] == "VideoUpscaleWriteBatch")
        assert plan["widgets_values"] == [57, 4]
        assert writer["widgets_values"] == ["overwrite", 0]
    # Guard against accidentally embedding the unsafe whole-video topology.
    assert [n["type"] for n in base["nodes"]] == [n["type"] for n in fp16["nodes"]]


def test_7b_smoke_test_is_exactly_two_seconds_at_24fps():
    path = WORKFLOW.with_name("SeedVR2_7B_FP16_SmokeTest_2s_24fps_6000_96GB.json")
    data = json.loads(path.read_text())
    prepare = next(n for n in data["nodes"] if n["type"] == "VideoLoopPrepare")
    plan = next(n for n in data["nodes"] if n["type"] == "VideoUpscaleBatchPlan")
    assert prepare["widgets_values"][1:4] == [24, 0, 2]
    assert plan["widgets_values"] == [60, 0]


def test_h3_video_reference_workflow_has_real_video_and_character_edges():
    path = WORKFLOW.with_name("MiniMax_H3_Video_Reference_Plus_Character_Image.json")
    data = json.loads(path.read_text())
    nodes = {n["id"]: n for n in data["nodes"]}
    h3 = next(n for n in data["nodes"] if n["type"] == "MiniMaxH3ReferenceToVideo")
    inputs = {i["name"]: i for i in h3["inputs"]}
    assert inputs["ref_images.ref_image_0"]["link"] is not None
    assert inputs["ref_videos.ref_video_0"]["link"] is not None
    assert inputs["ref_video_audios.ref_video_audio_0"]["link"] is not None
    assert any(n["type"] == "LoadVideo" for n in data["nodes"])
    assert any(n["type"] == "GetVideoComponents" for n in data["nodes"])
    for link_id, src, out_slot, dst, in_slot, _ in data["links"]:
        assert link_id in nodes[src]["outputs"][out_slot]["links"]
        assert nodes[dst]["inputs"][in_slot]["link"] == link_id


def test_h3_pose_character_replacement_hides_source_rgb_from_identity_conditioning():
    path = WORKFLOW.with_name("MiniMax_H3_Pose_Control_Character_Replacement.json")
    data = json.loads(path.read_text())
    nodes = {n["id"]: n for n in data["nodes"]}
    h3 = next(n for n in data["nodes"] if n["type"] == "MiniMaxH3ReferenceToVideo")
    inputs = {i["name"]: i for i in h3["inputs"]}
    assert inputs["ref_images.ref_image_0"]["link"] is not None
    assert inputs.get("ref_videos.ref_video_0", {}).get("link") is None
    control = next(n for n in data["nodes"] if n["type"] == "MiniMaxH3FunControlNetApply")
    assert next(i for i in control["inputs"] if i["name"] == "control_video")["link"] is not None
    for link_id, src, out_slot, dst, in_slot, _ in data["links"]:
        assert link_id in nodes[src]["outputs"][out_slot]["links"]
        assert nodes[dst]["inputs"][in_slot]["link"] == link_id


def test_h3_pose_subgraph_proxy_widgets_do_not_include_socket_inputs():
    path = WORKFLOW.with_name("MiniMax_H3_Pose_Control_Character_Replacement.json")
    data = json.loads(path.read_text())
    pose = next(n for n in data["nodes"] if n["id"] == 700)
    # resize_target_longer_size and scale_method are top-level socket inputs, not
    # serialized widgets. Including them shifts class/checkpoint/unet by two.
    assert pose["widgets_values"] == [
        True, True, True, True, 4, 2, 0.51, 0.5, "person", 2,
        "sdpose_wholebody_fp16.safetensors",
        "rt_detr_v4-x-hgnet_fp16.safetensors",
    ]
