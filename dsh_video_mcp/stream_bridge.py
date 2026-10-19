"""Bridge to the isolated VideoChat3 process; no heavyweight imports in MCP."""
from __future__ import annotations
import json, math, os, pathlib, queue, subprocess, threading, time


def selected_backend(root):
    config=root/'backend.json'
    name=json.loads(config.read_text(encoding='utf-8')).get('backend','qwen') if config.exists() else 'qwen'
    if name not in {'qwen','videochat3'}:raise ValueError('Unsupported backend in backend.json')
    return name


def stream_analysis(event):
    start=event['start_seconds'];end=event['end_seconds'];state=event['state'];text=event['text']
    if not isinstance(text,str) or len(text)>4000 or state not in {'silence','standby','response','unclassified','caption'}:
        raise ValueError('Invalid stream observation')
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (start,end)) or start>=end:
        raise ValueError('Invalid stream interval')
    notes=['Timestamps bound the observation window, not exact event onset. Streaming history is bounded; older events may be forgotten.']
    if state not in {'response','caption'}:notes.append('This round did not produce a confirmed response; silence/standby does not prove no event occurred.')
    if event.get('metrics',{}).get('stop_reason') in {'character_budget','token_budget'}:notes.append('Caption reached the length budget and may be incomplete.')
    if state=='unclassified':notes.append('Model omitted the expected streaming state tag.')
    return {'start_seconds':start,'end_seconds':end,'analysis':{'summary':text or f'Stream state: {state}',
        'events':[],'stream_state':state,'uncertainties':notes,'time_basis':'original-video observation window'},
        'timing':{'inference_seconds':event['inference_seconds'],**event.get('metrics',{})}}


def stop_backend(proc):
    if proc.poll() is not None:return
    if os.name=='nt':
        taskkill=pathlib.Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/taskkill.exe'
        subprocess.run([str(taskkill),'/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else:proc.terminate()
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()


def observations(root,path,source,request,start,end,on_status):
    python=root/'.venv-videochat3/Scripts/python.exe';model=root/'models/VideoChat3-4B'
    if not python.is_file() or not (model/'model.safetensors.index.json').is_file():
        raise RuntimeError('VideoChat3 runtime is not installed; run dsh-video-install-streaming --home <runtime-directory>')
    settings={'source':str(source),'model_dir':str(model),'question':request['question'],
              'start_seconds':start,'end_seconds':end,'fps':request['fps'],'stream_mode':request.get('stream_mode','caption')}
    request_file=path/'stream-request.json';request_file.write_text(json.dumps(settings,ensure_ascii=False),encoding='utf-8')
    env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONIOENCODING='utf-8')
    messages=queue.Queue(maxsize=4);proc=None
    with (path/'videochat3.log').open('ab',buffering=0) as log:
        try:
            proc=subprocess.Popen([str(python),'-u',str(pathlib.Path(__file__).with_name('videochat3_runner.py')),'--request',str(request_file)],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=log,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            (path/'backend-process.json').write_text(json.dumps({'pid':proc.pid}),encoding='utf-8')
            def read():
                try:
                    while True:
                        line=proc.stdout.readline(65537)
                        if not line:break
                        if len(line)>65536:messages.put(ValueError('Oversized backend message'));return
                        messages.put(line)
                except Exception as exc:messages.put(exc)
                finally:messages.put(None)
            thread=threading.Thread(target=read,daemon=True);thread.start()
            deadline=time.monotonic()+3600;finished=False;last=start
            while True:
                if (path/'cancel').exists():raise RuntimeError('Cancelled')
                if time.monotonic()>deadline:raise RuntimeError('VideoChat3 backend timed out')
                try:item=messages.get(timeout=.2)
                except queue.Empty:continue
                if item is None:break
                if isinstance(item,Exception):raise item
                event=json.loads(item)
                if event.get('type')=='ready':on_status(status='analyzing',backend_load_seconds=event['load_seconds'],backend_gpu_memory_bytes=event['gpu_memory_bytes'])
                elif event.get('type')=='observation':
                    analysis=stream_analysis(event)
                    if not start<=analysis['start_seconds']<analysis['end_seconds']<=end+.05 or analysis['start_seconds']<last-.05:
                        raise RuntimeError('Backend returned an out-of-range/non-monotonic observation')
                    last=analysis['end_seconds'];yield analysis
                elif event.get('type')=='finished':finished=True;on_status(backend_elapsed_seconds=event['elapsed_seconds'],backend_peak_gpu_bytes=event['gpu_peak_bytes'])
                else:raise RuntimeError('Unknown backend event')
            proc.wait(timeout=20)
            if proc.returncode or not finished or last<end-.1:
                detail=(path/'videochat3.log').read_bytes()[-1800:].decode('utf-8',errors='replace')
                raise RuntimeError('VideoChat3 did not complete the requested interval; videochat3.log: '+detail)
        finally:
            if proc is not None:
                stop_backend(proc)
                if proc.stdout:proc.stdout.close()
