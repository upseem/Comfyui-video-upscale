import sys
from types import ModuleType
import pytest
from src.comfyui_video_upscale.loop_bridge import loop_backend


def test_missing_dependency(monkeypatch):
    nodes = ModuleType('nodes')
    nodes.NODE_CLASS_MAPPINGS = {}
    monkeypatch.setitem(sys.modules, 'nodes', nodes)
    with pytest.raises(RuntimeError, match='Install upseem'):
        loop_backend()


def test_arbitrary_plugin_module_name(monkeypatch):
    nodes = ModuleType('nodes')
    extension = ModuleType('custom_nodes.any_folder.extension')
    core = ModuleType('custom_nodes.any_folder.core')
    prepare = type('VideoLoopPrepare', (), {'__module__': extension.__name__})
    writer = type('VideoLoopWriteFrame', (), {})
    extension.JOB_ROOT = '/example/jobs'
    extension.VideoLoopWriteFrame = writer
    nodes.NODE_CLASS_MAPPINGS = {'VideoLoopPrepare':prepare, 'VideoLoopWriteFrame':writer}
    for module in [nodes, extension, core]:
        monkeypatch.setitem(sys.modules, module.__name__, module)
    assert loop_backend() == (extension, core)
