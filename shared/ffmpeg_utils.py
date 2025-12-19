"""
FFmpeg Utilities Module

Provides a clean Python interface for FFmpeg operations used by both
the AI automation pipeline and the Manual Video Editor.

All operations are executed via subprocess to ensure cross-platform
compatibility and avoid binary dependencies beyond FFmpeg itself.
"""

import subprocess
import json
import os
import shutil
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class VideoMetadata:
    """Container for video file metadata."""
    duration: float          # Duration in seconds
    width: int              # Frame width in pixels
    height: int             # Frame height in pixels
    fps: float              # Frames per second
    codec: str              # Video codec name
    bitrate: Optional[int]  # Bitrate in bits/second
    rotation: int           # Rotation in degrees (0, 90, 180, 270)


@dataclass
class AudioMetadata:
    """Container for audio file/track metadata."""
    duration: float         # Duration in seconds
    sample_rate: int        # Sample rate in Hz
    channels: int           # Number of audio channels
    codec: str              # Audio codec name


def get_ffmpeg_path() -> str:
    """
    Finds the FFmpeg binary path.
    Checks local directory first, then system PATH.
    """
    # Check local directory (bundled with app)
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    
    # Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    
    raise FileNotFoundError(
        "FFmpeg not found. Please install FFmpeg or place it in the application directory."
    )


def get_ffprobe_path() -> str:
    """
    Finds the FFprobe binary path.
    Checks local directory first, then system PATH.
    """
    local_ffprobe = os.path.join(os.getcwd(), "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if os.path.exists(local_ffprobe):
        return local_ffprobe
    
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe
    
    raise FileNotFoundError(
        "FFprobe not found. Please install FFmpeg/FFprobe or place it in the application directory."
    )


def get_video_metadata(file_path: str) -> VideoMetadata:
    """
    Extracts video metadata using FFprobe.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        VideoMetadata object with video properties
        
    Raises:
        FileNotFoundError: If file doesn't exist
        RuntimeError: If FFprobe fails to parse the file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")
    
    ffprobe = get_ffprobe_path()
    
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFprobe failed: {e.stderr}")
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse FFprobe output")
    
    # Find video stream
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break
    
    if not video_stream:
        raise RuntimeError(f"No video stream found in: {file_path}")
    
    # Parse frame rate (can be "30/1" or "29.97")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = map(float, fps_str.split("/"))
        fps = num / den if den != 0 else 30.0
    else:
        fps = float(fps_str)
    
    # Get rotation from side_data or tags
    rotation = 0
    if "side_data_list" in video_stream:
        for side_data in video_stream["side_data_list"]:
            if "rotation" in side_data:
                rotation = int(side_data["rotation"])
    if "tags" in video_stream and "rotate" in video_stream["tags"]:
        rotation = int(video_stream["tags"]["rotate"])
    
    # Get duration from format or stream
    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0 and "duration" in video_stream:
        duration = float(video_stream["duration"])
    
    return VideoMetadata(
        duration=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        codec=video_stream.get("codec_name", "unknown"),
        bitrate=int(data.get("format", {}).get("bit_rate", 0)) or None,
        rotation=abs(rotation) % 360
    )


def get_audio_metadata(file_path: str) -> Optional[AudioMetadata]:
    """
    Extracts audio metadata using FFprobe.
    
    Args:
        file_path: Path to the audio/video file
        
    Returns:
        AudioMetadata object or None if no audio stream found
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    ffprobe = get_ffprobe_path()
    
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a:0",  # First audio stream
        file_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    
    streams = data.get("streams", [])
    if not streams:
        return None
    
    audio_stream = streams[0]
    
    return AudioMetadata(
        duration=float(audio_stream.get("duration", 0)),
        sample_rate=int(audio_stream.get("sample_rate", 44100)),
        channels=int(audio_stream.get("channels", 2)),
        codec=audio_stream.get("codec_name", "unknown")
    )


def extract_frame(
    file_path: str,
    time_seconds: float,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None
) -> bool:
    """
    Extracts a single frame from a video at the specified time.
    
    Args:
        file_path: Path to source video
        time_seconds: Time position in seconds
        output_path: Path for output image (jpg/png)
        width: Optional resize width
        height: Optional resize height
        
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_ffmpeg_path()
    
    cmd = [
        ffmpeg,
        "-y",  # Overwrite output
        "-ss", str(time_seconds),  # Seek before input (fast)
        "-i", file_path,
        "-vframes", "1",  # Extract one frame
        "-q:v", "2",  # High quality
    ]
    
    # Add scaling if specified
    if width and height:
        cmd.extend(["-vf", f"scale={width}:{height}"])
    elif width:
        cmd.extend(["-vf", f"scale={width}:-1"])
    elif height:
        cmd.extend(["-vf", f"scale=-1:{height}"])
    
    cmd.append(output_path)
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def generate_proxy(
    input_path: str,
    output_path: str,
    width: int = 640,
    quality: int = 28
) -> bool:
    """
    Generates a low-resolution proxy video for faster playback.
    
    Args:
        input_path: Path to source video
        output_path: Path for proxy video
        width: Target width (height auto-calculated)
        quality: CRF quality (higher = smaller file, lower quality)
        
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_ffmpeg_path()
    
    cmd = [
        ffmpeg,
        "-y",
        "-i", input_path,
        "-vf", f"scale={width}:-2",  # -2 ensures even height
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", str(quality),
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def trim_video(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    reencode: bool = False
) -> bool:
    """
    Trims a video to the specified time range.
    
    Args:
        input_path: Path to source video
        output_path: Path for trimmed video
        start_time: Start time in seconds
        end_time: End time in seconds
        reencode: If True, re-encodes video (slower but frame-accurate)
        
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_ffmpeg_path()
    duration = end_time - start_time
    
    if reencode:
        cmd = [
            ffmpeg,
            "-y",
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]
    else:
        # Stream copy (fast but may have keyframe issues)
        cmd = [
            ffmpeg,
            "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path
        ]
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def concat_videos(
    input_files: List[str],
    output_path: str,
    reencode: bool = True
) -> bool:
    """
    Concatenates multiple video files into one.
    
    Args:
        input_files: List of input video paths
        output_path: Path for output video
        reencode: If True, re-encodes (required if videos have different properties)
        
    Returns:
        True if successful, False otherwise
    """
    if not input_files:
        return False
    
    if len(input_files) == 1:
        # Just copy the single file
        shutil.copy2(input_files[0], output_path)
        return True
    
    ffmpeg = get_ffmpeg_path()
    
    if reencode:
        # Use filter_complex for re-encoding
        filter_inputs = ""
        filter_concat = ""
        for i in range(len(input_files)):
            filter_concat += f"[{i}:v][{i}:a]"
        filter_concat += f"concat=n={len(input_files)}:v=1:a=1[outv][outa]"
        
        cmd = [ffmpeg, "-y"]
        for f in input_files:
            cmd.extend(["-i", f])
        cmd.extend([
            "-filter_complex", filter_concat,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ])
    else:
        # Create concat demuxer file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for input_file in input_files:
                # Escape single quotes in paths
                escaped = input_file.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
            concat_file = f.name
        
        cmd = [
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def mix_audio(
    video_path: str,
    audio_files: List[Tuple[str, float, float]],  # (path, start_time, volume)
    output_path: str
) -> bool:
    """
    Mixes additional audio tracks into a video.
    
    Args:
        video_path: Path to source video
        audio_files: List of (audio_path, start_time, volume) tuples
        output_path: Path for output video
        
    Returns:
        True if successful, False otherwise
    """
    if not audio_files:
        # No audio to mix, just copy
        shutil.copy2(video_path, output_path)
        return True
    
    ffmpeg = get_ffmpeg_path()
    
    # Build filter complex for audio mixing
    cmd = [ffmpeg, "-y", "-i", video_path]
    
    filter_parts = []
    audio_inputs = []
    
    for i, (audio_path, start_time, volume) in enumerate(audio_files):
        cmd.extend(["-i", audio_path])
        input_idx = i + 1
        
        # Delay and volume adjust
        delay_ms = int(start_time * 1000)
        filter_parts.append(
            f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},volume={volume}[a{i}]"
        )
        audio_inputs.append(f"[a{i}]")
    
    # Combine original audio with new tracks
    all_audio = "[0:a]" + "".join(audio_inputs)
    filter_parts.append(
        f"{all_audio}amix=inputs={len(audio_files) + 1}:duration=first:dropout_transition=2[aout]"
    )
    
    filter_complex = ";".join(filter_parts)
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ])
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_name: str = "Arial",
    font_size: int = 24,
    font_color: str = "white",
    outline_color: str = "black",
    outline_width: int = 2
) -> bool:
    """
    Burns SRT subtitles into a video.
    
    Args:
        video_path: Path to source video
        srt_path: Path to SRT subtitle file
        output_path: Path for output video
        font_name: Font family name
        font_size: Font size in points
        font_color: Font color (name or hex)
        outline_color: Outline color
        outline_width: Outline thickness
        
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_ffmpeg_path()
    
    # Escape path for subtitle filter (Windows paths need special handling)
    escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    
    subtitle_filter = (
        f"subtitles='{escaped_srt}':"
        f"force_style='FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,"  # White in ASS format
        f"OutlineColour=&H00000000,"  # Black outline
        f"Outline={outline_width},"
        f"Shadow=1,"
        f"Alignment=2,"  # Center bottom
        f"MarginV=30'"
    )
    
    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        output_path
    ]
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return os.path.exists(output_path)
    except subprocess.CalledProcessError:
        return False


def get_video_duration(file_path: str) -> float:
    """
    Quick method to get just the video duration.
    
    Args:
        file_path: Path to video file
        
    Returns:
        Duration in seconds
    """
    try:
        metadata = get_video_metadata(file_path)
        return metadata.duration
    except Exception:
        return 0.0
