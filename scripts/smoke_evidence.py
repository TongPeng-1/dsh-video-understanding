"""Real MCP/GPU integration check. Supply your own local video; no media is published."""
import argparse, asyncio, base64, io, json, pathlib, sys, time
from PIL import Image
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main(args):
    root=pathlib.Path(args.install_dir).resolve()
    params=StdioServerParameters(command=str(root/'.venv/Scripts/python.exe'),args=[str(root/'server.py')])
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            r=await client.call_tool('analyze_video',{'source':str(pathlib.Path(args.video).resolve()),'question':'请只根据可见画面说明物体的颜色、场景和动作先后，不要猜测配音。','fps':2,'transcribe':True})
            job=json.loads(r.content[0].text)['job_id'];print('Submitted',job,flush=True)
    # A new connection checks that the job survives the submitting client closing.
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize();deadline=time.monotonic()+600;state=None
            while time.monotonic()<deadline:
                r=await client.call_tool('get_video_job',{'job_id':job})
                if r.isError:raise RuntimeError(r.content[0].text)
                status=json.loads(r.content[0].text)
                if state!=status['status']:state=status['status'];print(state,flush=True)
                if state in {'completed','failed','cancelled'}:break
                await asyncio.sleep(5)
            assert state=='completed',status
            bundle=status['result']['evidence_bundle']
            assert bundle['independent_visual_observation']
            assert bundle['visual_text']
            assert status['result']['channels']['speech']['status']=='completed'
            assert bundle['speech_text']
            images=[c for c in r.content if c.type=='image'];assert images
            checks=[]
            for image in images:
                with Image.open(io.BytesIO(base64.b64decode(image.data))) as decoded:
                    checks.append({'format':decoded.format,'size':decoded.size});decoded.verify()
            output={'job_id':job,'status':status,'image_checks':checks}
            destination=root/'tests/three-channel-smoke.json';destination.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'job_id':job,'visual_text':bundle['visual_text'],'speech_text':bundle['speech_text'],'images':checks},ensure_ascii=True),flush=True)
            print('PASS actual text + image MCP content; evidence saved locally.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--install-dir',required=True);parser.add_argument('--video',required=True)
    asyncio.run(main(parser.parse_args()))
