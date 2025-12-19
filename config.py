import os
import json
import shutil
import logging
from pathlib import Path

# --- CONSTANTS ---
APP_NAME = "LazyCut"
VERSION = "2.0.0"
SERVER_URL = "http://localhost:8000/process_script"  # Change to cloud URL in production
GITHUB_REPO = "HarperKollins/LazyCut"
TEMP_DIR = os.path.join(os.getcwd(), "temp")
IS_WINDOWS = os.name == 'nt'

# --- PATHS ---
# Use %APPDATA% on Windows, ~/.config on Linux/Mac
if os.name == 'nt':
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], APP_NAME)
else:
    CONFIG_DIR = os.path.join(str(Path.home()), ".config", APP_NAME)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
BROLL_FOLDER = os.path.join(os.getcwd(), "brolls")

# --- LOGGING ---
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("lazycut.log", mode='w')
        ]
    )
    return logging.getLogger(APP_NAME)

logger = setup_logging()

# --- BINARY DISCOVERY ---
def get_binary_path(binary_name):
    """
    Finds the path to a binary (ffmpeg, magick) using shutil.which.
    """
    path = shutil.which(binary_name)
    if not path:
        # Common fallback paths for Windows
        if os.name == 'nt':
            common_paths = [
                f"C:\\Program Files\\{binary_name}\\{binary_name}.exe",
                f"C:\\ffmpeg\\bin\\{binary_name}.exe",
                f"C:\\Program Files\\ImageMagick-7.1.2-Q16\\{binary_name}.exe"
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
    return path

FFMPEG_BINARY = get_binary_path("ffmpeg")
IMAGEMAGICK_BINARY = get_binary_path("magick")

# Check for critical binaries
if not FFMPEG_BINARY:
    logger.warning("⚠️ FFmpeg not found! Video processing will fail.")

if not IMAGEMAGICK_BINARY:
    logger.warning("ImageMagick not found! Text rendering may fail.")

# --- SETTINGS MANAGER ---
def load_settings():
    """Loads settings from JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return {}

def save_settings(key, value):
    """Saves a single setting key-value pair."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    
    settings = load_settings()
    settings[key] = value
    
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info(f"Saved setting: {key} = {value}")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

def get_setting(key, default=None):
    """Retrieves a setting value."""
    settings = load_settings()
    return settings.get(key, default)
