"""Resolve the installed loop extension at execution time, regardless of folder name.

Uses the tested loop repository's internal disk helpers. This compatibility
bridge must be rechecked when upgrading that dependency.
"""
import importlib


def loop_backend():
    import nodes
    prepare = nodes.NODE_CLASS_MAPPINGS.get('VideoLoopPrepare')
    writer = nodes.NODE_CLASS_MAPPINGS.get('VideoLoopWriteFrame')
    if prepare is None or writer is None:
        raise RuntimeError(
            'Install upseem/ComfyUI_video_loop and restart ComfyUI. '
            'VideoLoopPrepare and VideoLoopWriteFrame are required.'
        )
    extension = importlib.import_module(prepare.__module__)
    if not hasattr(extension, 'JOB_ROOT') or not hasattr(extension, 'VideoLoopWriteFrame'):
        raise RuntimeError('Unsupported ComfyUI_video_loop version: disk API changed')
    core = importlib.import_module(prepare.__module__.rsplit('.', 1)[0] + '.core')
    return extension, core
