import os
from moviepy.editor import VideoFileClip

# Path to the user's video
video_path = r"C:\Users\ASUS\Desktop\fff\WhatsApp Video 2025-11-26 at 01.48.05.mp4"

try:
    clip = VideoFileClip(video_path)
    print(f"Video: {os.path.basename(video_path)}")
    print(f"Resolution: {clip.w}x{clip.h}")
    print(f"Aspect Ratio: {clip.aspect_ratio}")
    print(f"Duration: {clip.duration}")
    
    # Check for rotation in metadata
    if hasattr(clip, 'rotation'):
        print(f"Rotation attribute: {clip.rotation}")
    else:
        print("No 'rotation' attribute found on clip object.")
        
    # Check ffmpeg metadata if possible
    if clip.reader.infos:
        print(f"FFmpeg Infos: {clip.reader.infos}")

    clip.close()

except Exception as e:
    print(f"Error: {e}")
