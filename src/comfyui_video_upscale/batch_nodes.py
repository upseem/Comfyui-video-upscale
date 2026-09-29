from __future__ import annotations

import json
import os
import numpy as np
import torch
from PIL import Image
from comfy_api.v0_0_2 import io
from .batching import chunk_plan, validate_plan
from .loop_bridge import loop_backend


def job(value):
    backend, core = loop_backend()
    paths = core.resolve_job(backend.JOB_ROOT, value)
    manifest = json.loads(paths.manifest.read_text())
    return paths, manifest


class VideoUpscaleBatchPlan(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='VideoUpscaleBatchPlan', category='Video Upscale/Batch', inputs=[
            io.Int.Input('frame_count', force_input=True, min=1),
            io.Int.Input('chunk_size', default=49, min=1, max=4096),
            io.Int.Input('context', default=8, min=0, max=128),
        ], outputs=[io.Int.Output('chunk_count'), io.Int.Output('chunk_size'), io.Int.Output('context')])

    @classmethod
    def execute(cls, frame_count, chunk_size=49, context=8):
        chunk_plan(frame_count, 0, chunk_size, context)
        return io.NodeOutput((frame_count + chunk_size - 1)//chunk_size, chunk_size, context)


class VideoUpscaleReadBatch(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='VideoUpscaleReadBatch', category='Video Upscale/Batch', inputs=[
            io.String.Input('job_directory', force_input=True),
            io.Int.Input('chunk_index', force_input=True, default=0, min=0),
            io.Int.Input('chunk_size', force_input=True, default=49, min=1),
            io.Int.Input('context', force_input=True, default=8, min=0),
        ], outputs=[io.Image.Output('images'), io.String.Output('batch_receipt')])

    @classmethod
    def execute(cls, job_directory, chunk_index, chunk_size=49, context=8):
        paths, manifest = job(job_directory)
        plan = chunk_plan(manifest['frame_count'], chunk_index, chunk_size, context)
        frames = []
        for index in range(plan['read_start'], plan['read_end']):
            with Image.open(paths.input_frames / f'{index:08d}.png') as image:
                frames.append(np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0)
        receipt = dict(job_directory=str(paths.root), plan=plan)
        return io.NodeOutput(torch.from_numpy(np.stack(frames)), json.dumps(receipt))

    @classmethod
    def fingerprint_inputs(cls, job_directory, chunk_index, chunk_size=49, context=8):
        try:
            paths, manifest = job(job_directory)
            plan = chunk_plan(manifest['frame_count'], chunk_index, chunk_size, context)
            _, core = loop_backend()
            return tuple(core.file_fingerprint(paths.input_frames / f'{i:08d}.png')
                         for i in range(plan['read_start'], plan['read_end']))
        except (ValueError, OSError):
            return float('NaN')


class VideoUpscaleWriteBatch(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='VideoUpscaleWriteBatch', category='Video Upscale/Batch', inputs=[
            io.String.Input('job_directory', force_input=True),
            io.String.Input('batch_receipt', force_input=True),
            io.Image.Input('images'),
            io.Combo.Input('existing', options=['overwrite', 'skip_valid', 'fail']),
            io.Int.Input('png_compress_level', default=0, min=0, max=9,
                         tooltip='0 is fastest and largest; 3 is a balanced archival default.'),
        ], outputs=[io.String.Output('write_receipt')], is_output_node=True, not_idempotent=True)

    @classmethod
    def execute(cls, job_directory, batch_receipt, images, existing='overwrite', png_compress_level=0):
        paths, manifest = job(job_directory)
        receipt = json.loads(batch_receipt)
        if receipt['job_directory'] != str(paths.root):
            raise ValueError('Batch receipt belongs to a different job')
        plan = receipt['plan']
        validate_plan(plan, manifest['frame_count'], images.shape[0])
        if images.ndim != 4 or images.shape[-1] != 3:
            raise ValueError('Expected RGB IMAGE tensor [frames, height, width, 3]')
        # Save one frame at a time: never materialize the entire output as numpy.
        skipped = 0
        for offset in range(plan['keep_count']):
            i = plan['trim_left'] + offset
            frame_index = plan['start'] + offset
            target = paths.output_frames / f'{frame_index:08d}.png'
            if target.exists():
                if existing == 'fail':
                    raise FileExistsError(target)
                if existing == 'skip_valid':
                    try:
                        with Image.open(target) as old:
                            old.verify()
                        skipped += 1
                        continue
                    except OSError:
                        pass
            array = images[i].detach().cpu().clamp(0, 1).numpy()
            temporary = target.with_name(f'.{target.name}.{os.getpid()}.tmp.png')
            Image.fromarray(np.uint8(array * 255.0)).save(
                temporary, compress_level=png_compress_level)
            os.replace(temporary, target)
            del array
        return io.NodeOutput(json.dumps(dict(
            start=plan['start'], end=plan['end'], skipped=skipped,
            png_compress_level=png_compress_level,
            context_policy='trim', job_directory=str(paths.root))))
