import importlib.util
import pathlib
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

if __name__ == '__main__':
    unittest.main()
