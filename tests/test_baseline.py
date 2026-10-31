import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('video_server', ROOT / 'dsh_video_mcp/server.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)

class BaselineTests(unittest.TestCase):
    def test_private_url_rejected(self):
        with patch('socket.getaddrinfo', return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError):
                video.validate_url('https://example.com/video.mp4')

    def test_bad_job_ids_rejected(self):
        for value in ['../secret', 'x'*32, 'A'*32]:
            with self.assertRaises(ValueError):
                video.job_path(value)

    def test_invalid_ranges_rejected_before_spawn(self):
        for start,end,fps in [(float('nan'),1,2),(-1,2,2),(5,2,2),(0,3,99)]:
            with self.assertRaises(ValueError):
                video.submit('missing.mp4','question',start,end,fps,False)

class FrameArgumentTests(unittest.TestCase):
    """get_video_frame_result timestamp validation and persistence (no ffmpeg run)."""

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.jobs=self.root/'jobs';self.job_id='b'*32;self.job=self.jobs/self.job_id
        self.job.mkdir(parents=True)
        self.clip=self.root/'clip.mp4';self.clip.write_bytes(b'0')  # existence checked; ffmpeg is mocked
        video.save(self.job/'status.json',{'status':'completed','job_id':self.job_id})
        video.save(self.job/'source.json',{'path':str(self.clip)})
        video.save(self.job/'request.json',{'source':str(self.clip),'question':'q','start_seconds':0,'end_seconds':30,'fps':2,'transcribe':True,'backend':'qwen','stream_mode':'caption','detail':False})
        self.override=patch.object(video,'JOBS',self.jobs);self.override.start()
        self.probe=patch.object(video,'probe',return_value=(60.0,False));self.probe.start()
        # A tiny valid PNG so image decode paths run.
        self.png=io.BytesIO();video.Image.new('RGB',(64,48),(1,2,3)).save(self.png,format='PNG');self.png=self.png.getvalue()
    def tearDown(self):
        self.probe.stop();self.override.stop();self.temp.cleanup()

    def test_batch_limits_and_validation(self):
        with patch.object(video,'run_bytes',return_value=self.png):
            result=video.get_video_frame_result(self.job_id,[1.0,2.5])
            images=[b for b in result.content if getattr(b,'type',None)=='image']
            self.assertEqual(len(images),2)
            with self.assertRaises(ValueError):
                video.get_video_frame_result(self.job_id,[1.0]*9)
            with self.assertRaises(ValueError):
                video.get_video_frame_result(self.job_id,[float('nan')])
            with self.assertRaises(ValueError):
                video.get_video_frame_result(self.job_id,[-1.0])
            with self.assertRaises(ValueError):
                video.get_video_frame_result(self.job_id,61.0)  # beyond probed duration 60s
            # Persisted metadata matches delivered frames.
            meta=json.loads((self.job/'frame-meta.json').read_text(encoding='utf-8'))
            self.assertEqual(len(meta),2)
            self.assertEqual(meta[0]['timestamp_seconds'],1.0)
            self.assertTrue((self.job/meta[0]['file']).is_file())

    def test_no_frame_at_timestamp_reported_not_fatal(self):
        with patch.object(video,'run_bytes',return_value=b''):
            result=video.get_video_frame_result(self.job_id,5.0)
            self.assertTrue(any('no decodable frame' in b.text for b in result.content if getattr(b,'type',None)=='text'))
            self.assertFalse(any(getattr(b,'type',None)=='image' for b in result.content))

    def test_region_crop_and_max_edge(self):
        with patch.object(video,'run_bytes',return_value=self.png):
            result=video.get_video_frame_result(self.job_id,3.0,max_edge=1920,region=[0.25,0.25,0.75,0.75])
            meta=result.structuredContent['frames'][0]
            # 64x48 source cropped to the middle half -> 32x24, then capped by max_edge (no upscale).
            self.assertEqual((meta['width'],meta['height']),(32,24))
            self.assertEqual(meta['region'],[0.25,0.25,0.75,0.75])
            self.assertEqual(meta['source_width'],64)
            for bad_region in ([0.5,0.5,0.3,0.6],[-0.1,0,1,1],[0,0,1],[0,0,0.01,1],['a',0,1,1]):
                with self.assertRaises(ValueError):
                    video.get_video_frame_result(self.job_id,1.0,region=bad_region)
            for bad_edge in (100,4000,1280.5,True):
                with self.assertRaises(ValueError):
                    video.get_video_frame_result(self.job_id,1.0,max_edge=bad_edge)

if __name__ == '__main__':
    unittest.main()
