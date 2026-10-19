import pathlib
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_baseline import video

class LifecycleTests(unittest.TestCase):
    def test_worker_uses_running_interpreter_and_explicit_home(self):
        with tempfile.TemporaryDirectory(prefix='video home ') as home:
            with patch.object(video,'ROOT',pathlib.Path(home)):
                command=video.worker_command('a'*32)
                self.assertEqual(command[0],video.sys.executable)
                self.assertEqual(command[1],str(video.CODE_ROOT/'server.py'))
                self.assertEqual(command[2:],['--home',home,'--worker','a'*32])
                self.assertNotEqual(pathlib.Path(command[1]).parent,video.ROOT)

    def test_failed_start_releases_backend(self):
        with tempfile.TemporaryDirectory() as home:
            root=pathlib.Path(home);binary=root/'runtime/llama-cuda13/llama-server.exe'
            binary.parent.mkdir(parents=True);binary.touch()
            job=root/'job';job.mkdir()
            process=Mock();process.poll.return_value=1
            client=Mock()
            with patch.object(video,'ROOT',root),patch.object(video.subprocess,'Popen',return_value=process),patch.object(video.httpx,'Client',return_value=client):
                with self.assertRaisesRegex(RuntimeError,'failed to start'):
                    video.start_llama(job,2)
            process.terminate.assert_called_once();process.wait.assert_called_once()
            client.close.assert_called_once()

    def test_loading_waits_for_health_before_returning_backend(self):
        with tempfile.TemporaryDirectory() as home:
            root=pathlib.Path(home);binary=root/'runtime/llama-cuda13/llama-server.exe'
            binary.parent.mkdir(parents=True);binary.touch();job=root/'job';job.mkdir()
            process=Mock();process.poll.return_value=None
            unavailable=Mock(status_code=503);ready=Mock(status_code=200)
            models=Mock();models.json.return_value={'data':[{'architecture':{'input_modalities':['video']}}]}
            client=Mock();client.get.side_effect=[unavailable,ready,models]
            with patch.object(video,'ROOT',root),patch.object(video.subprocess,'Popen',return_value=process),patch.object(video.httpx,'Client',return_value=client),patch.object(video.time,'sleep'):
                proc,connection,log=video.start_llama(job,2)
            self.assertIs(proc,process);self.assertIs(connection,client)
            self.assertEqual(client.get.call_count,3)
            video.stop_model(proc,connection,log)
