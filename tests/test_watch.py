import pathlib,tempfile,unittest
from dsh_video_mcp.watch_service import validate_clip

class WatchInputTests(unittest.TestCase):
    def test_clip_must_be_owned_bounded_and_have_finite_player_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);source=root/'1.webm';source.write_bytes(b'x'*64)
            good={'path':str(source),'start':10,'end':12,'seq':1,'epoch':0}
            self.assertEqual(validate_clip(good,root),source.resolve())
            with self.assertRaises(ValueError):validate_clip({**good,'start':float('nan')},root)
            with self.assertRaises(ValueError):validate_clip({**good,'end':30},root)
            with self.assertRaises(ValueError):validate_clip(good,root/'different-owner')

if __name__=='__main__':unittest.main()
