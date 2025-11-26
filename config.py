import os
import sys
import platform
import shutil
import logging

# --- LOGGING SETUP ---
def setup_logging():
    logger = logging.getLogger('LazyCut')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logging()

# --- DETERMINE PATHS ---
# 1. APP_DIR: Where the code/exe lives (READ ONLY in Program Files)
if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. WORK_DIR: Where we save files (READ/WRITE PERMISSION)
# We use %APPDATA% (e.g., C:\Users\You\AppData\Roaming\LazyCut)
USER_DATA = os.path.join(os.getenv('APPDATA'), "LazyCut")

# Define folders inside the Safe Zone
INPUT_DIR = os.path.join(USER_DATA, "input")
OUTPUT_DIR = os.path.join(USER_DATA, "output")
BROLLS_DIR = os.path.join(USER_DATA, "brolls")
ASSETS_DIR = os.path.join(USER_DATA, "assets")
TEMP_DIR = os.path.join(USER_DATA, "temp")
BROLL_FOLDER = BROLLS_DIR # Alias for core.py compatibility

# Create them safely
dirs = [INPUT_DIR, OUTPUT_DIR, BROLLS_DIR, ASSETS_DIR, TEMP_DIR]
for d in dirs:
    os.makedirs(d, exist_ok=True)

# --- PATHS TO BINARIES ---
current_os = platform.system()
IS_WINDOWS = current_os == 'Windows'

if current_os == "Windows":
    # Look for binaries in the Installation Folder (APP_DIR)
    # When frozen, sys._MEIPASS contains the bundled files.
    IM_PATH = os.path.join(APP_DIR, "magick.exe")
    FFMPEG_PATH = os.path.join(APP_DIR, "ffmpeg.exe")
    
    # Fallback for Dev Mode (Script run)
    if not getattr(sys, 'frozen', False):
        # Check local folder
        local_magick = os.path.join(os.getcwd(), "magick.exe")
        if os.path.exists(local_magick):
            IM_PATH = local_magick
        else:
             # Check common install locations
            possible_paths = [
                r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe",
                r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    IM_PATH = p
                    break
        
        local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            FFMPEG_PATH = local_ffmpeg
        else:
            sys_ffmpeg = shutil.which("ffmpeg")
            if sys_ffmpeg: FFMPEG_PATH = sys_ffmpeg

else:
    IM_PATH = shutil.which("magick") or shutil.which("convert")
    FFMPEG_PATH = shutil.which("ffmpeg")

IMAGEMAGICK_BINARY = IM_PATH

# --- APP INFO ---
APP_NAME = "LazyCut"
VERSION = "2.0.0"
GITHUB_REPO = "HarperKollins/LazyCut"
