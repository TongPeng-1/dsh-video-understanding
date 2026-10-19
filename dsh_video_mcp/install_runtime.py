"""Download the pinned, tested Windows runtime. Does not modify DSH settings."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, pathlib, time, zipfile
import httpx

ROOT = pathlib.Path(os.environ.get('DSH_VIDEO_HOME',pathlib.Path(os.environ.get('LOCALAPPDATA',pathlib.Path.home()))/'dsh-video-understanding')).expanduser().resolve()
REV = '1cd86afb9a95c410a6038ab3b40d8b578c892266'
ARTIFACTS = [
    ('https://github.com/ggml-org/llama.cpp/releases/download/b11669/llama-b11669-bin-win-cuda-13.4-x64.zip?download=1', 'runtime/llama-cuda13.zip', '3b92d5c064f5032e603e531d3ec8961f3bd6613e5dfad047399a92dec8e95dbc'),
    ('https://github.com/ggml-org/llama.cpp/releases/download/b11669/cudart-llama-bin-win-cuda-13.4-x64.zip?download=1', 'runtime/cudart-cuda13.zip', '738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668'),
    # Release URLs may be updated upstream. A changed hash fails closed; do not bypass it.
    ('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', 'runtime/ffmpeg.zip', '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'),
    (f'https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/{REV}/Qwen3VL-4B-Instruct-Q4_K_M.gguf?download=true', 'models/Qwen3VL-4B-Instruct-Q4_K_M.gguf', '66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a'),
    (f'https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/{REV}/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf?download=true', 'models/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf', '30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d'),
]

def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def download(item):
    url, name, digest = item
    target = ROOT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and sha256(target) == digest:
        return target
    temporary = target.with_suffix(target.suffix + '.partial')
    for attempt in range(3):
        try:
            with httpx.stream('GET', url, follow_redirects=True, timeout=180) as response:
                response.raise_for_status()
                with temporary.open('wb') as output:
                    for block in response.iter_bytes(1024 * 1024):
                        output.write(block)
            if sha256(temporary) != digest:
                raise RuntimeError(f'Official SHA-256 mismatch: {name}')
            temporary.replace(target)
            print('Verified', name, flush=True)
            return target
        except (httpx.HTTPError, OSError, RuntimeError):
            if attempt == 2:
                raise
            time.sleep(2)

def extract_checked(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            output = (destination / member.filename).resolve()
            if not output.is_relative_to(root):
                raise ValueError('Archive path escapes destination')
        package.extractall(destination)

def main(argv=None):
    global ROOT
    parser=argparse.ArgumentParser(description='Install pinned Windows video runtime and models. Explicit download; never runs on MCP startup.')
    parser.add_argument('--home',default=str(ROOT))
    ns=parser.parse_args(argv)
    ROOT=pathlib.Path(ns.home).expanduser().resolve()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, ARTIFACTS))
    for name in ['llama-cuda13.zip', 'cudart-cuda13.zip']:
        extract_checked(ROOT / 'runtime' / name, ROOT / 'runtime/llama-cuda13')
    with zipfile.ZipFile(ROOT / 'runtime/ffmpeg.zip') as archive:
        destination = ROOT / 'runtime/ffmpeg'
        destination.mkdir(exist_ok=True)
        for name in archive.namelist():
            if name.endswith(('/ffmpeg.exe', '/ffprobe.exe')):
                (destination / pathlib.Path(name).name).write_bytes(archive.read(name))
    from huggingface_hub import snapshot_download
    snapshot_download('Systran/faster-whisper-small', local_dir=ROOT / 'models/whisper-small', allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt', 'preprocessor_config.json'])
    (ROOT / 'verified-artifacts.json').write_text(json.dumps({name: digest for _, name, digest in ARTIFACTS}, indent=2), encoding='utf-8')
    print('Runtime installed. Configure DSH separately using examples/desktop.patch.yml.')

if __name__ == '__main__':
    main()
