import pytest
from src.comfyui_video_upscale.batching import chunk_plan, validate_plan


@pytest.mark.parametrize('count', [1, 4, 5, 17, 48, 49, 50, 98, 101, 1000])
@pytest.mark.parametrize('size', [1, 17, 49])
@pytest.mark.parametrize('context', [0, 8, 64])
def test_exact_coverage(count, size, context):
    indices = []
    for i in range((count+size-1)//size):
        plan = chunk_plan(count, i, size, context)
        validate_plan(plan, count, plan['read_count'])
        read = list(range(plan['read_start'], plan['read_end']))
        kept = read[plan['trim_left']:plan['trim_left']+plan['keep_count']]
        indices.extend(kept)
        assert 0 <= plan['read_start'] < plan['read_end'] <= count
    assert indices == list(range(count))


def test_reject_corrupt_plan_and_changed_count():
    plan = chunk_plan(100, 1, 49, 8)
    with pytest.raises(ValueError):
        validate_plan(plan, 100, plan['read_count']-1)
    with pytest.raises(ValueError):
        validate_plan({**plan, 'start':0}, 100, plan['read_count'])


@pytest.mark.parametrize('args', [(0,0,49,8),(10,-1,49,8),(10,1,49,8),(10,0,0,8),(10,0,49,-1)])
def test_invalid(args):
    with pytest.raises(ValueError):
        chunk_plan(*args)
