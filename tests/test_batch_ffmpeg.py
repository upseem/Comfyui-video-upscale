"""CPU-only frame bookkeeping smoke test; deliberately does not test AI inference."""
import json
import shutil
import subprocess

import pytest
from src.comfyui_video_upscale.batching import chunk_plan


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
def test_fractional_fps_audio_and_frame_order(tmp_path):
    def run(*args):
        subprocess.run(['ffmpeg','-y','-v','error',*map(str,args)], check=True)
    source=tmp_path/'source.mp4'
    src=tmp_path/'input'; dst=tmp_path/'output'
    src.mkdir(); dst.mkdir()
    run('-f','lavfi','-i','testsrc2=size=64x48:rate=30000/1001',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
        '-t','2','-c:v','libx264','-c:a','aac',source)
    run('-i',source,'-vf','fps=30000/1001','-start_number','0',src/'%08d.png')
    count=len(list(src.glob('*.png')))
    for i in range((count+16)//17):
        p=chunk_plan(count,i,17,8)
        # Identity processor stands in for SeedVR2; ensure context isn't written twice.
        read=[src/f'{j:08d}.png' for j in range(p['read_start'],p['read_end'])]
        for offset,path in enumerate(read[p['trim_left']:p['trim_left']+p['keep_count']]):
            shutil.copyfile(path,dst/f"{p['start']+offset:08d}.png")
    for i in range(count):
        assert (src/f'{i:08d}.png').read_bytes()==(dst/f'{i:08d}.png').read_bytes()
    result=tmp_path/'result.mp4'
    run('-framerate','30000/1001','-start_number','0','-i',dst/'%08d.png',
        '-i',source,'-map','0:v:0','-map','1:a:0','-c:v','libx264',
        '-pix_fmt','yuv420p','-c:a','aac','-shortest',result)
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(result)]))
    video=next(s for s in data['streams'] if s['codec_type']=='video')
    assert int(video['nb_frames'])==count
    assert video['avg_frame_rate']=='30000/1001'
    assert any(s['codec_type']=='audio' for s in data['streams'])
