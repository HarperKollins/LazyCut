import os
import logging
import json
import torch
import glob
import soundfile as sf
import google.generativeai as genai
from dotenv import load_dotenv
from colorlog import ColoredFormatter
import PIL.Image
import warnings
import uuid
import concurrent.futures
import threading

# --- 🛠️ COMPATIBILITY FIXES ---
warnings.filterwarnings("ignore")
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
from moviepy.config import change_settings

# --- 🎨 IMAGEMAGICK CONFIG ---
IM_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe"
if os.path.exists(IM_PATH):
    change_settings({"IMAGEMAGICK_BINARY": IM_PATH})

# --- 1. SETUP ---
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Logging
formatter = ColoredFormatter(
    "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
    datefmt=None,
    reset=True,
    log_colors={'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red'}
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger('LazyCut')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

import whisper

# --- 2. GLOBAL RESOURCES ---
logger.info("🔌 Loading Whisper (Global)...")
whisper_model = whisper.load_model("base")
vad_file_lock = threading.Lock() 

# --- 3. PRO CAPTIONS ---
def generate_pro_captions(text_segments, video_w, video_h):
    caption_clips = []
    FONT_SIZE = int(video_h * 0.07) 
    STROKE_WIDTH = 3
    
    for seg in text_segments:
        text = seg['text'].strip().upper()
        start = seg['start']
        end = seg['end']
        duration = end - start
        
        if duration < 0.1: continue 

        txt_clip = TextClip(
            text,
            fontsize=FONT_SIZE,
            font="Arial-Bold",
            color='white',
            stroke_color='black',
            stroke_width=STROKE_WIDTH,
            method='caption',     
            size=(int(video_w * 0.85), None)
        )
        
        txt_clip = txt_clip.set_position(('center', 0.75), relative=True)
        txt_clip = txt_clip.set_start(0).set_duration(duration)
        caption_clips.append(txt_clip)
        
    return caption_clips

# --- 4. WORKER FUNCTION ---
def process_single_video(v_path, folder_path):
    fname = os.path.basename(v_path)
    unique_id = str(uuid.uuid4())[:8]
    temp_audio = os.path.join(folder_path, f"temp_{unique_id}.wav")
    
    try:
        video = VideoFileClip(v_path)
        if video.audio is None:
            video.close()
            return None

        video.audio.write_audiofile(temp_audio, fps=16000, verbose=False, logger=None)
        video.close()
        
        if os.path.getsize(temp_audio) < 1000: 
            vad_data = []
        else:
            with vad_file_lock:
                model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                              model='silero_vad',
                                              force_reload=False,
                                              onnx=False)
            (get_speech_timestamps, _, _, _, _) = utils
            data, samplerate = sf.read(temp_audio)
            if len(data) == 0:
                vad_data = []
            else:
                wav = torch.FloatTensor(data)
                if len(wav.shape) > 1: wav = wav[:, 0]
                speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
                vad_data = [{'start': st['start']/16000, 'end': st['end']/16000} for st in speech_timestamps]

        try:
            transcription = whisper_model.transcribe(v_path)
            segments = transcription["segments"]
        except:
            segments = []

        if os.path.exists(temp_audio): os.remove(temp_audio)
        logger.info(f"✅ Processed: {fname}")
        return {"filename": fname, "filepath": v_path, "segments": segments, "vad": vad_data}

    except Exception as e:
        logger.error(f"❌ Error on {fname}: {e}")
        return None

# --- 5. FOLDER HUNTER ---
def find_newest_video_batch():
    IGNORE_LIST = ['.git', '.venv', 'venv', '__pycache__', '.idea', '.vscode', 'output', 'archive']
    all_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and d not in IGNORE_LIST]
    if not all_dirs: return None, None
    all_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    for folder in all_dirs:
        videos = glob.glob(os.path.join(folder, "*.mp4"))
        videos = [v for v in videos if "FINAL_" not in v]
        if videos:
            logger.info(f"📂 Detected Batch: '{folder}' ({len(videos)} videos)")
            return folder, videos
    return None, None

# --- 6. THE DIRECTOR ---
def get_director_cut(library):
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    all_sentences = []
    global_id = 0
    
    for video in library:
        for seg in video['segments']:
            all_sentences.append({
                "global_id": global_id,
                "filename": video['filename'],
                "text": seg['text'],
                "start": seg['start'],
                "end": seg['end']
            })
            global_id += 1

    prompt = f"""
    You are a Video Editor. 
    TASK: Create a PUNCHY video.
    
    RULES:
    1. NO DUPLICATES. Keep only the BEST version of repeated lines.
    2. STORY: Hook -> Pain -> Solution -> CTA.
    
    SENTENCES:
    {json.dumps(all_sentences, indent=2)}

    RETURN JSON: {{ "selected_sequence": [ID_LIST] }}
    """
    
    try:
        logger.info(f"🧠 The Director is thinking...")
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "")
        data = json.loads(text)
        return data.get("selected_sequence", []), all_sentences
    except Exception as e:
        logger.error(f"Director Error: {e}")
        return [], []

# --- 7. THE ASSEMBLER (CPU SAFE MODE) ---
def render_story(sequence_ids, all_sentences, full_library, folder_path):
    logger.info(f"🏗️ Assembling Story & Captions...")
    
    final_clips = []
    open_source_handles = []
    is_zoomed = False
    file_map = {v['filename']: {'path': v['filepath'], 'vad': v['vad']} for v in full_library}
    
    try:
        for seq_id in sequence_ids:
            sentence = next((s for s in all_sentences if s['global_id'] == seq_id), None)
            if not sentence: continue
            
            filename = sentence['filename']
            if filename not in file_map: continue
            
            file_data = file_map[filename]
            full_path = file_data['path']
            file_vad = file_data['vad']
            
            w_start = sentence['start']
            w_end = sentence['end']
            
            refined_start, refined_end = w_start, w_end
            relevant_vad = [v for v in file_vad if (v['start'] >= w_start - 0.8) and (v['end'] <= w_end + 0.8)]
            if relevant_vad:
                refined_start = relevant_vad[0]['start']
                refined_end = relevant_vad[-1]['end']
            
            source_video = VideoFileClip(full_path)
            open_source_handles.append(source_video)
            
            final_start = max(0, refined_start - 0.05)
            final_end = min(source_video.duration, refined_end + 0.1)
            if (final_end - final_start) < 0.3: continue

            clip = source_video.subclip(final_start, final_end)
            clip = clip.audio_fadein(0.05).audio_fadeout(0.05)
            
            if is_zoomed:
                clip = clip.resize(height=int(source_video.h * 1.2))
                clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=source_video.w, height=source_video.h)
            
            txt_segment = [{"text": sentence['text'], "start": 0, "end": clip.duration}]
            captions = generate_pro_captions(txt_segment, source_video.w, source_video.h)
            
            if captions:
                clip = CompositeVideoClip([clip] + captions).set_duration(clip.duration)

            is_zoomed = not is_zoomed
            final_clips.append(clip)

        if not final_clips: 
            logger.error("❌ No clips generated.")
            return

        output_file = os.path.join(folder_path, "FINAL_PRO_EDIT.mp4")
        if os.path.exists(output_file):
            try: os.remove(output_file)
            except: pass

        logger.info(f"🎞️ Rendering (CPU Safe Mode) to: {output_file}")
        
        final_video = concatenate_videoclips(final_clips, method="compose")
        
        # --- CPU SAFE SETTINGS ---
        final_video.write_videofile(
            output_file, 
            codec="libx264", 
            audio_codec="aac", 
            preset="medium", # Slower but better quality/easier on CPU
            fps=24, 
            verbose=False, 
            logger=None
        )
        logger.info(f"✅ DONE! Saved in '{folder_path}'")

    except Exception as e:
        logger.error(f"Render failed: {e}")
        
    finally:
        logger.info("🧹 Cleaning up...")
        for v in open_source_handles:
            try: v.close()
            except: pass

# --- 8. MAIN ---
def start_lazycut():
    folder_path, video_files = find_newest_video_batch()
    if not folder_path:
        logger.error("❌ No video folders found!")
        return

    logger.info(f"🚀 Processing {len(video_files)} videos...")
    
    full_library = []
    # Limit to 2 workers to save CPU during analysis
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(process_single_video, v, folder_path) for v in video_files]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                full_library.append(result)
    
    sequence_ids, all_sentences = get_director_cut(full_library)
    
    if sequence_ids:
        render_story(sequence_ids, all_sentences, full_library, folder_path)

if __name__ == "__main__":
    start_lazycut()