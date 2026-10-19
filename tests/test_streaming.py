import io,json,pathlib,unittest,tempfile
from unittest.mock import patch,Mock
from test_baseline import video
from dsh_video_mcp import stream_bridge
from dsh_video_mcp.videochat3_compat import tie_checkpoint_output,generation_inputs,caption_stop_reason,prepare_checkpoint_class,install_presampled_video_processor
from dsh_video_mcp.videochat3_runner import observation,verify_model_code

class StreamTests(unittest.TestCase):
    def test_streaming_tags_are_not_confused_with_no_event(self):
        event=observation('</Silence>',4,8,.2);analysis=stream_bridge.stream_analysis(event)
        self.assertEqual(analysis['analysis']['stream_state'],'silence')
        self.assertFalse(analysis['analysis']['events'])
        self.assertTrue(any('does not prove' in n for n in analysis['analysis']['uncertainties']))
        response=observation('</Response> red square moves',8,12,.6)
        self.assertEqual(stream_bridge.stream_analysis(response)['analysis']['summary'],'red square moves')
    def test_missing_tag_is_reported(self):
        analysis=stream_bridge.stream_analysis(observation('unclassified text',0,4,.5))
        self.assertEqual(analysis['analysis']['stream_state'],'unclassified')
        self.assertTrue(any('omitted' in n for n in analysis['analysis']['uncertainties']))
    def test_unverified_model_code_cannot_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'Unverified'):verify_model_code(pathlib.Path(tmp))
    def test_backend_config_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.assertEqual(stream_bridge.selected_backend(root),'qwen')
            (root/'backend.json').write_text(json.dumps({'backend':'arbitrary-command'}))
            with self.assertRaises(ValueError):stream_bridge.selected_backend(root)
    def test_stream_cursor_advances_and_empty_poll_preserves_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs=pathlib.Path(tmp);job_id='a'*32;job=jobs/job_id;job.mkdir()
            video.save(job/'status.json',{'job_id':job_id,'status':'analyzing'})
            event=observation('</Standby>',0,4,.5);analysis=stream_bridge.stream_analysis(event);analysis['keyframes']=[]
            video.save(job/'result.json',{'schema_version':2,'channels':{'visual':{'independent':True}},'segments':[analysis],'transcript':[]})
            with patch.object(video,'JOBS',jobs):
                first=video.get_job_result(job_id,image_limit=0).structuredContent['result']
                self.assertEqual(first['stream_cursor'],1);self.assertTrue(first['stream_active'])
                empty=video.get_job_result(job_id,segment_offset=1,image_limit=0).structuredContent['result']
                self.assertEqual(empty['segments'],[]);self.assertEqual(empty['stream_cursor'],1)
                video.save(job/'status.json',{'job_id':job_id,'status':'completed'})
                self.assertFalse(video.get_job_result(job_id).structuredContent['result']['stream_active'])

    def test_cancel_stops_only_the_owned_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);python=root/'.venv-videochat3/Scripts/python.exe';python.parent.mkdir(parents=True);python.touch()
            model=root/'models/VideoChat3-4B';model.mkdir(parents=True);(model/'model.safetensors.index.json').touch()
            job=root/'job';job.mkdir();(job/'cancel').touch()
            process=Mock(pid=42,stdout=io.BytesIO(b''));process.poll.return_value=None
            with patch.object(stream_bridge.subprocess,'Popen',return_value=process),patch.object(stream_bridge,'stop_backend') as stop:
                with self.assertRaisesRegex(RuntimeError,'Cancelled'):
                    list(stream_bridge.observations(root,job,root/'source.mp4',{'question':'observe','fps':2,'transcript':'secret ASR must not reach vision'},0,4,lambda **kw:None))
            stop.assert_called_once_with(process)
            self.assertTrue(process.stdout.closed)
            sent=json.loads((job/'stream-request.json').read_text(encoding='utf-8'))
            self.assertNotIn('transcript',sent)
            self.assertNotIn('secret ASR',json.dumps(sent))

    def test_missing_output_weights_are_tied_to_trained_embeddings(self):
        model=Mock();model.config.text_config.tie_word_embeddings=True
        trained=object();model.get_input_embeddings.return_value.weight=trained
        tie_checkpoint_output(model,{'missing_keys':['lm_head.weight']})
        self.assertIs(model.lm_head.weight,trained)
        with self.assertRaises(RuntimeError):tie_checkpoint_output(model,{'missing_keys':['language_model.layer.weight']})
    def test_first_step_keeps_images_and_cached_step_omits_images(self):
        image=object();cache=Mock();cache.get_seq_length.return_value=0
        base=Mock(side_effect=lambda *a,**k:{'input_ids':'tokens','pixel_values':image,'pixel_values_videos':image})
        first=generation_inputs(Mock(),'tokens',base,cache)
        self.assertIs(first['pixel_values'],image)
        cache.get_seq_length.return_value=100
        following=generation_inputs(Mock(),'tokens',base,cache)
        self.assertIsNone(following['pixel_values']);self.assertIsNone(following['pixel_values_videos'])

    def test_caption_mode_is_distinct_from_native_proactive_response(self):
        event=observation('visible red square',0,4,.5,mode='caption')
        self.assertEqual(event['state'],'caption');self.assertIsNone(event['protocol_valid'])
        self.assertEqual(stream_bridge.stream_analysis(event)['analysis']['summary'],'visible red square')
        with self.assertRaises(ValueError):video.submit('missing.mp4','watch',0,4,2,False,'invalid')

    def test_caption_budget_stops_generation_at_a_sentence_or_length(self):
        self.assertEqual(caption_stop_reason('红色方块静止。'),'sentence')
        self.assertIsNone(caption_stop_reason('速度是10.5'))
        self.assertEqual(caption_stop_reason('字'*48),'character_budget')
        self.assertIsNone(caption_stop_reason('正在移动'))
    def test_presampled_video_keeps_metadata_and_pinned_patch_layout(self):
        processor=Mock();vp=processor.video_processor
        tensor=Mock(ndim=4,shape=(8,3,168,280));metadata=object()
        vp._decode_and_sample_videos.return_value=([tensor],[metadata]);vp._preprocess.return_value={}
        vp.image_mean=vp.image_std=[.5]*3;vp.patch_size=14;vp.temporal_patch_size=1;vp.merge_size=2
        install_presampled_video_processor(processor)
        out=vp.preprocess([tensor],video_metadata=[metadata],do_resize=False,do_sample_frames=False)
        self.assertEqual(out['video_metadata'],[metadata])
        self.assertEqual(vp._preprocess.call_args.kwargs['patch_size'],14)
        self.assertEqual(vp._preprocess.call_args.kwargs['image_mean'],[.5]*3)
        with self.assertRaises(ValueError):vp.preprocess([tensor],do_resize=True,do_sample_frames=False)

    def test_token_limited_caption_is_incomplete_evidence(self):
        event=observation('unfinished caption',0,4,.5,mode='caption')
        event['metrics']={'stop_reason':'token_budget'}
        self.assertTrue(any('incomplete' in n for n in stream_bridge.stream_analysis(event)['analysis']['uncertainties']))

    def test_checkpoint_is_tied_before_initialization(self):
        config=Mock();config.text_config.tie_word_embeddings=True;cls=Mock()
        prepare_checkpoint_class(cls,config)
        self.assertTrue(config.tie_word_embeddings)
        self.assertEqual(cls._tied_weights_keys,{'lm_head.weight':'model.language_model.embed_tokens.weight'})

if __name__=='__main__':unittest.main()
