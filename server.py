"""Compatibility launcher for existing DSH direct-script configurations."""
import os
import pathlib
from dsh_video_mcp.server import main

if __name__ == '__main__':
    # Existing source/deployed installations keep their adjacent runtime directory.
    home=os.environ.get('DSH_VIDEO_HOME',str(pathlib.Path(__file__).resolve().parent))
    main(['--home',home,*__import__('sys').argv[1:]])
