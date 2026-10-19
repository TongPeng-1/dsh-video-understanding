"""Prepare the optional VideoChat3 environment without changing existing models."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,shutil,subprocess

def main(argv=None):
    default=pathlib.Path(os.environ.get('DSH_VIDEO_HOME',pathlib.Path(os.environ.get('LOCALAPPDATA',pathlib.Path.home()))/'dsh-video-understanding'))
    parser=argparse.ArgumentParser();parser.add_argument('--home',default=str(default));parser.add_argument('--activate',action='store_true');args=parser.parse_args(argv)
    root=pathlib.Path(args.home).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    uv=shutil.which('uv')
    if not uv:raise RuntimeError('Install uv first; this installer creates an isolated Python 3.12 environment.')
    package=pathlib.Path(__file__).resolve().parent;python=root/'.venv-videochat3/Scripts/python.exe'
    if not python.exists():subprocess.run([uv,'venv','--python','3.12',str(python.parents[1])],check=True)
    subprocess.run([uv,'pip','install','--python',str(python),'-r',str(package/'requirements-videochat3.lock.txt')],check=True)
    os.environ['HF_HUB_DISABLE_XET']='1'
    from huggingface_hub import snapshot_download
    manifest=json.loads((package/'videochat3-manifest.json').read_text(encoding='utf-8'))
    model=root/'models/VideoChat3-4B'
    snapshot_download(manifest['repository'],revision=manifest['revision'],local_dir=str(model),max_workers=4)
    for name,info in manifest['weights'].items():
        with (model/name).open('rb') as handle:actual=hashlib.file_digest(handle,'sha256').hexdigest()
        if actual!=info['sha256']:raise RuntimeError('Model checksum failed: '+name)
    from .videochat3_runner import verify_model_code
    verify_model_code(model)
    if args.activate:
        config=root/'backend.json'
        if config.exists():shutil.copy2(config,root/'backend.before-videochat3.json')
        temporary=root/'backend.new.json';temporary.write_text(json.dumps({'backend':'videochat3'}),encoding='utf-8');os.replace(temporary,config)
    print('VideoChat3 installed. Run an inference check before relying on realtime speed. Activation:',args.activate)

if __name__=='__main__':main()
