"""Lazy entrypoint keeps CPU-only planning tools importable without ComfyUI."""

async def comfy_entrypoint():
    from comfy_api.v0_0_2 import ComfyExtension
    from .src.comfyui_video_upscale.batch_nodes import (
        VideoUpscaleBatchPlan, VideoUpscaleReadBatch, VideoUpscaleWriteBatch,
    )

    class VideoUpscaleExtension(ComfyExtension):
        async def get_node_list(self):
            return [VideoUpscaleBatchPlan, VideoUpscaleReadBatch, VideoUpscaleWriteBatch]

    return VideoUpscaleExtension()
