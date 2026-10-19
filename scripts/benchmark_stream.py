"""Measure first-result latency and full pipeline throughput through installed MCP."""
import argparse,asyncio,json,pathlib,time
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def run(args):
    root=pathlib.Path(args.home).resolve();begun=time.monotonic();first=None;cursor=0;images=0;states=[]
    output=pathlib.Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    errlog=output.with_suffix('.mcp.log').open('w',encoding='utf-8')
    params=StdioServerParameters(command=str(root/'.venv/Scripts/dsh-video-mcp.exe'),args=['--home',str(root)])
    async with stdio_client(params,errlog=errlog) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            runtime=await client.call_tool('video_runtime_status',{});assert not runtime.isError
            submitted=await client.call_tool('analyze_video',{'source':str(pathlib.Path(args.video).resolve()),'question':args.question,'transcribe':True,'fps':2})
            if submitted.isError:raise RuntimeError(submitted.content[0].text)
            job=json.loads(submitted.content[0].text)['job_id'];print('job',job,flush=True)
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline:
                response=await client.call_tool('get_video_job',{'job_id':job,'segment_offset':cursor,'image_limit':4})
                if response.isError:raise RuntimeError(response.content[0].text)
                status=json.loads(response.content[0].text)
                if not states or states[-1]!=status['status']:states.append(status['status']);print(status['status'],flush=True)
                if 'result' in status:
                    result=status['result'];segments=result['segments']
                    if segments and first is None:first=time.monotonic()-begun;print('first_result_seconds',round(first,2),flush=True)
                    images+=sum(block.type=='image' for block in response.content)
                    cursor=result['stream_cursor']
                if status['status'] in {'completed','failed','cancelled'}:break
                await asyncio.sleep(1)
            else:raise TimeoutError('Benchmark did not complete; job remains available by its ID')
            summary={'job_id':job,'status':status['status'],'wall_seconds':time.monotonic()-begun,'first_result_seconds':first,'observations':cursor,'image_blocks_received':images,'states':states,'backend_load_seconds':status.get('backend_load_seconds'),'backend_elapsed_seconds':status.get('backend_elapsed_seconds'),'backend_peak_gpu_bytes':status.get('backend_peak_gpu_bytes')}
            full=json.loads((root/'jobs'/job/'result.json').read_text(encoding='utf-8')) if (root/'jobs'/job/'result.json').exists() else {}
            summary.update(channels=full.get('channels'),video_range=full.get('range'),model=full.get('model'),caption_characters=[len(x['analysis'].get('summary','')) for x in full.get('segments',[])],round_inference_seconds=[x.get('timing',{}).get('inference_seconds') for x in full.get('segments',[])])
            if summary['video_range']:summary['realtime_factor']=summary['wall_seconds']/(full['range'][1]-full['range'][0])
            output=pathlib.Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(summary,ensure_ascii=True),flush=True)
            if status['status']!='completed':raise RuntimeError(status.get('error','Video job failed'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',required=True);p.add_argument('--video',required=True);p.add_argument('--output',required=True);p.add_argument('--timeout',type=int,default=1800);p.add_argument('--question',default='请持续报告截至当前看到的动作、场景及变化，简洁描述。')
    asyncio.run(run(p.parse_args()))
