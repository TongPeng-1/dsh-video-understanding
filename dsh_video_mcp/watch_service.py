"""Private stdio companion service: latest-window queue, resident GPU and CPU ASR."""
import argparse,concurrent.futures,json,os,pathlib,queue,subprocess,sys,threading,time
from . import server
from .stream_bridge import stop_backend

def emit(value):print(json.dumps(value,ensure_ascii=True),flush=True)

def validate_clip(item,storage):
    storage=storage.resolve()
    path=pathlib.Path(item['path']).resolve()
    if not path.is_relative_to(storage) or path.suffix!='.webm' or not 64<=path.stat().st_size<=4*1024*1024:raise ValueError('Invalid clip path or size')
    start=item['start'];end=item['end']
    if not all(isinstance(x,(int,float)) and __import__('math').isfinite(x) for x in [start,end]) or not 0<=start<end<=start+6:raise ValueError('Invalid playback interval')
    if not all(isinstance(item[k],int) and item[k]>=0 for k in ['seq','epoch']):raise ValueError('Invalid playback generation')
    return path

def main():
    from .videochat3_compat import configure_process_performance
    configure_process_performance()
    p=argparse.ArgumentParser();p.add_argument('--home',required=True);p.add_argument('--storage',required=True);a=p.parse_args()
    root=pathlib.Path(a.home).resolve();storage=pathlib.Path(a.storage).resolve();storage.mkdir(parents=True,exist_ok=True);server.configure_home(root)
    # Initialize NumPy/CTranslate2 native modules on the main thread. On this
    # Windows Python 3.13 runtime their first import in a pool thread can hang.
    from faster_whisper import WhisperModel
    incoming=queue.Queue(maxsize=1);stopping=threading.Event();events=queue.Queue(maxsize=2);proc=None
    def receive():
        try:
            for raw in sys.stdin:
                if len(raw)>8192:raise ValueError('Oversized command')
                item=json.loads(raw)
                if item.get('type')=='stop':break
                validate_clip(item,storage)
                try:incoming.put_nowait(item)
                except queue.Full:
                    try:
                        dropped=incoming.get_nowait()
                        validate_clip(dropped,storage).unlink(missing_ok=True)
                    except queue.Empty:pass
                    incoming.put_nowait(item)
        except Exception as exc:emit({'type':'error','error':str(exc)[:500]})
        finally:stopping.set();(storage/'cancel').touch()
    threading.Thread(target=receive,daemon=True).start()
    class Speech:
        model=None
        def prepare(self):
            if self.model is None:
                self.model=WhisperModel(str(server.ASR),device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,local_files_only=True)
        def transcribe(self,item,path):
            if not item.get('audio'):return {'status':'not_present','text':''}
            self.prepare()
            wav=path.with_suffix('.wav')
            server.run([server.FFMPEG,'-hide_banner','-loglevel','error','-y','-i',path,'-vn','-ac','1','-ar','16000',wav],timeout=20)
            parts,_=self.model.transcribe(str(wav),beam_size=1,vad_filter=True,condition_on_previous_text=False)
            return {'status':'completed','text':' '.join(s.text for s in parts)[:3000]}
    def next_event():
        deadline=time.monotonic()+90
        while not stopping.is_set():
            if time.monotonic()>deadline:raise TimeoutError('Resident visual worker timed out')
            try:
                value=events.get(timeout=.2)
                if value is None:raise RuntimeError('Resident visual worker exited')
                return value
            except queue.Empty:continue
        raise InterruptedError('Companion stopped')
    try:
        with server.gpu_lock(storage,lambda:stop_backend(proc) if proc is not None else None),concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,(storage/'visual.log').open('ab',buffering=0) as log:
            if stopping.is_set():return
            speech=Speech();speech_startup=pool.submit(speech.prepare)
            request=storage/'resident.json';request.write_text(json.dumps({'watch':True,'storage':str(storage),'model_dir':str(root/'models/VideoChat3-4B'),'question':'描述当前可见动作。','stream_mode':'caption'}),encoding='utf-8')
            env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONIOENCODING='utf-8')
            proc=subprocess.Popen([str(root/'.venv-videochat3/Scripts/python.exe'),'-u',str(pathlib.Path(__file__).with_name('videochat3_runner.py')),'--request',str(request)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,env=env,creationflags=server.NO_WINDOW,text=True,encoding='utf-8')
            def read_events():
                try:
                    for raw in proc.stdout:
                        if len(raw)>2*1024*1024:raise ValueError('Oversized visual evidence')
                        events.put(json.loads(raw))
                finally:events.put(None)
            threading.Thread(target=read_events,daemon=True).start()
            if next_event().get('type')!='ready':raise RuntimeError('Invalid visual startup')
            speech_startup.result(timeout=60)
            emit({'type':'ready'});last_seq=-1
            while not stopping.is_set():
                try:item=incoming.get(timeout=.2)
                except queue.Empty:continue
                if item['seq']<=last_seq:continue
                last_seq=item['seq'];path=validate_clip(item,storage);future=pool.submit(speech.transcribe,item,path)
                proc.stdin.write(json.dumps({'type':'clip','path':str(path),'seq':item['seq'],'epoch':item['epoch']})+'\n');proc.stdin.flush()
                evidence=next_event()
                try:transcript=future.result(timeout=15)
                except Exception as exc:transcript={'status':'failed','text':'','error':str(exc)[:300]}
                evidence.update(start=item['start'],end=item['end'],speech=transcript,independent=True)
                emit(evidence)
                path.unlink(missing_ok=True);path.with_suffix('.wav').unlink(missing_ok=True)
    except InterruptedError:pass
    except Exception as exc:emit({'type':'error','error':str(exc)[:800]})
    finally:
        if proc is not None:stop_backend(proc)
        emit({'type':'stopped'})

if __name__=='__main__':main()
