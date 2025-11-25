import os
import platform
import shutil
import logging
from pathlib import Path

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

# --- OS DETECTION ---
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'
IS_MAC = platform.system() == 'Darwin'

logger.info(f"🖥️ Detected OS: {platform.system()}")

# --- PATH MANAGEMENT ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT_DIR, 'assets')
BROLL_FOLDER = os.path.join(ROOT_DIR, 'brolls')
TEMP_DIR = os.path.join(ROOT_DIR, 'temp')

# Ensure directories exist
for d in [ASSETS_DIR, BROLL_FOLDER, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# --- BINARY PATHS ---
def get_imagemagick_path():
    # 1. Check Local Folder (For Portable/Bundled Mode)
    local_magick = os.path.join(os.getcwd(), "magick.exe")
    if os.path.exists(local_magick):
        logger.info(f"✅ Using Bundled ImageMagick: {local_magick}")
        return local_magick

    if IS_WINDOWS:
        # 2. Check common install locations
        # Try to find magick in PATH first
        path = shutil.which("magick")
        if path: return path
        
        # 3. Fallback to hardcoded Program Files (Legacy support)
        possible_paths = [
            r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe",
            r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
        ]
        for p in possible_paths:
            if os.path.exists(p):
                logger.info(f"⚠️ Using System ImageMagick: {p}")
                return p
        return None
    else:
        # On Linux/Mac, it's usually just 'convert' or 'magick' in PATH
        return shutil.which("magick") or shutil.which("convert")

def get_ffmpeg_path():
    # 1. Check Local Folder
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        logger.info(f"✅ Using Bundled FFmpeg: {local_ffmpeg}")
        return local_ffmpeg
    return shutil.which("ffmpeg")

IMAGEMAGICK_BINARY = get_imagemagick_path()
if not IMAGEMAGICK_BINARY:
    logger.warning("⚠️ ImageMagick not found! Text overlays might fail.")
else:
    logger.info(f"✅ ImageMagick found at: {IMAGEMAGICK_BINARY}")

# --- APP INFO ---
APP_NAME = "LazyCut"
VERSION = "2.0.0"
GITHUB_REPO = "HarperKollins/LazyCut"
