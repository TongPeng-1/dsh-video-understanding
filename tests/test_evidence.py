import base64
import inspect
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch,Mock

from test_baseline import video

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.jobs=self.root/'jobs';self.job_id='a'*32;self.job=self.jobs/self.job_id
        self.job.mkdir(parents=True);video.save(self.job/'status.json',{'status':'completed','job_id':self.job_id})
        self.override=patch.object(video,'JOBS',self.jobs);self.override.start()
    def tearDown(self):
        self.override.stop();self.temp.cleanup()
    def png(self,color='red'):
        stream=io.BytesIO();video.Image.new('RGB',(32,20),color).save(stream,format='PNG');return stream.getvalue()
    def frame(self,index=0,timestamp=1):
        target=self.job/'keyframes'/f'{index}.png';target.parent.mkdir(exist_ok=True)
        data=self.png();target.write_bytes(data)
        return {'id':str(index),'file':target.relative_to(self.job).as_posix(),'timestamp_seconds':timestamp,'width':32,'height':20,'sha256':video.hashlib.sha256(data).hexdigest()}
    def result(self,frames,legacy=False):
        result={'schema_version':1 if legacy else 2,'channels':{'visual':{'independent':not legacy}},'segments':[{'start_seconds':0,'end_seconds':10,'analysis':{'summary':'visual only','events':[]},'keyframes':frames}], 'transcript':[{'start_seconds':1,'end_seconds':2,'text':'speech only'},{'start_seconds':20,'end_seconds':21,'text':'other segment'}]}
        video.save(self.job/'result.json',result)
    def test_visual_api_has_no_asr_parameter(self):
        self.assertNotIn('transcript',inspect.signature(video.infer).parameters)
        class Response:
            def raise_for_status(self):pass
            def json(self):return {'choices':[{'message':{'content':'{"summary":"visual","events":[{"start_seconds":1,"end_seconds":2}],"answer":"relative","uncertainties":[]}'}}]}
        class Client:
            def post(self,url,json):self.payload=json;return Response()
        clip=self.root/'test.mp4';clip.write_bytes(b'test-video')
        client=Client();result=video.infer(client,clip,'what is visible?',30,38)
        self.assertEqual(client.payload['messages'][0]['content'][0]['type'],'input_video')
        self.assertEqual(result['analysis']['events'][0]['start_seconds'],31)
        self.assertNotIn('speech_evidence',client.payload['response_format']['schema']['properties']['events']['items']['properties'])
    def test_three_channels_and_actual_images(self):
        self.result([self.frame()])
        result=video.get_job_result(self.job_id)
        bundle=result.structuredContent['result']['evidence_bundle']
        self.assertIn('visual only',bundle['visual_text'])
        self.assertIn('speech only',bundle['speech_text'])
        self.assertNotIn('other segment',bundle['speech_text'])
        self.assertTrue(bundle['independent_visual_observation'])
        images=[c for c in result.content if c.type=='image']
        self.assertEqual(len(images),1)
        self.assertEqual(base64.b64decode(images[0].data),self.png())
        self.assertEqual(json.loads(result.content[0].text),result.structuredContent)
    def test_image_pagination_and_no_silent_drop(self):
        self.result([self.frame(i) for i in range(6)])
        first=video.get_job_result(self.job_id)
        self.assertEqual(len([c for c in first.content if c.type=='image']),4)
        self.assertEqual(first.structuredContent['result']['evidence_bundle']['next_image_offset'],4)
        second=video.get_job_result(self.job_id,image_offset=4)
        self.assertEqual(second.structuredContent['result']['evidence_bundle']['delivered_image_ids'],['4','5'])
        self.assertIsNone(second.structuredContent['result']['evidence_bundle']['next_image_offset'])
    def test_images_can_be_omitted_explicitly(self):
        self.result([self.frame()]);result=video.get_job_result(self.job_id,image_limit=0)
        self.assertEqual([c.type for c in result.content],['text'])
        self.assertEqual(result.structuredContent['result']['evidence_bundle']['delivered_image_ids'],[])
    def test_path_escape_rejected(self):
        frame=self.frame();frame['file']='../outside.png'
        with self.assertRaises(ValueError):video.read_frame(self.job,frame)
    def test_changed_image_rejected(self):
        frame=self.frame();(self.job/frame['file']).write_bytes(self.png('blue'))
        with self.assertRaises(ValueError):video.read_frame(self.job,frame)
    def test_invalid_image_rejected_even_with_matching_hash(self):
        frame=self.frame();data=b'not a png';(self.job/frame['file']).write_bytes(data);frame['sha256']=video.hashlib.sha256(data).hexdigest()
        with self.assertRaises(Exception):video.read_frame(self.job,frame)
    def test_legacy_results_are_not_claimed_independent(self):
        self.result([],legacy=True);result=video.get_job_result(self.job_id)
        bundle=result.structuredContent['result']['evidence_bundle']
        self.assertFalse(bundle['independent_visual_observation']);self.assertIn('legacy_notice',bundle)
    def test_change_pair_is_selected(self):
        frames=[bytes([0])*96*96*3]*4+[bytes([255])*96*96*3]*4
        with patch.object(video,'run_bytes',return_value=b''.join(frames)):
            times=video.keyframe_times('test.mp4',0,8)
        self.assertIn((4,'largest_visible_change'),times)
        self.assertIn((3.4,'before_visible_change'),times)
        self.assertEqual(len(times),4)
    def test_invalid_pagination_rejected(self):
        for args in [(-1,4,0,4),(0,0,0,4),(0,4,-1,4),(0,4,0,5)]:
            with self.assertRaises(ValueError):video.get_job_result(self.job_id,*args)
    def test_speech_failure_is_explicit_and_does_not_rewrite_vision(self):
        video.save(self.job/'request.json',{'source':'test.mp4','question':'what is visible?','start_seconds':0,'end_seconds':8,'fps':2,'transcribe':True})
        asr=self.root/'asr';asr.mkdir();(asr/'model.bin').write_bytes(b'test')
        proc=Mock();proc.poll.return_value=0;client=Mock();log=Mock();log.closed=True
        analysis={'start_seconds':0,'end_seconds':8,'analysis':{'summary':'independent observation','events':[]}}
        with patch.object(video,'gpu_lock',side_effect=lambda *a,**k:nullcontext()),patch.object(video,'acquire_source',return_value=self.root/'source.mp4'),patch.object(video,'probe',return_value=(8,True)),patch.object(video,'ASR',asr),patch.object(video,'transcribe_audio',side_effect=RuntimeError('synthetic ASR failure')),patch.object(video,'start_llama',return_value=(proc,client,log)),patch.object(video,'run',return_value=''),patch.object(video,'infer',return_value=analysis),patch.object(video,'extract_keyframes',return_value=[]):
            video.worker(self.job_id)
        result=json.loads((self.job/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(result['channels']['speech']['status'],'failed')
        self.assertIn('synthetic ASR failure',result['channels']['speech']['error'])
        self.assertEqual(result['channels']['visual']['status'],'completed')
        self.assertEqual(result['segments'][0]['analysis']['summary'],'independent observation')

if __name__=='__main__':unittest.main()
