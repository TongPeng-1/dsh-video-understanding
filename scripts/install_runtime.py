"""Compatibility launcher for source installations."""
import pathlib, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from dsh_video_mcp.install_runtime import main
if __name__ == '__main__':
    main(['--home',str(pathlib.Path(__file__).resolve().parents[1]),*sys.argv[1:]])
