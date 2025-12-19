"""
FFmpeg Command Graph Builder

Builds complex FFmpeg filter graphs from timeline data.
Translates the abstract timeline representation into concrete
FFmpeg commands for export.

The builder creates deterministic, reproducible command graphs
that can be inspected and debugged.
"""

import os
import tempfile
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from manual_editor.models.project import Project, Clip, AudioClip


@dataclass
class TrimmedClip:
    """Represents a trimmed segment of source video."""
    source_file: str
    in_time: float
    out_time: float
    timeline_start: float
    
    @property
    def duration(self) -> float:
        return self.out_time - self.in_time


@dataclass
class ExportSettings:
    """Export configuration."""
    output_path: str
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    video_codec: str = "libx264"
    video_preset: str = "medium"
    video_crf: int = 18
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    burn_subtitles: bool = True


class FFmpegGraphBuilder:
    """
    Builds FFmpeg command graphs from timeline data.
    
    The builder takes a Project and generates the necessary
    FFmpeg commands to render the final video. It handles:
    - Video clip trimming and concatenation
    - Audio track mixing
    - Subtitle burning
    
    The process is split into stages:
    1. Prepare trimmed clips
    2. Build filter complex for video
    3. Build filter complex for audio
    4. Add subtitle filter
    5. Generate final command
    """
    
    def __init__(self):
        self._temp_dir = tempfile.mkdtemp(prefix="lazycut_export_")
    
    def build_export_command(
        self,
        project: "Project",
        settings: ExportSettings,
        srt_path: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Build the complete FFmpeg command for export.
        
        Args:
            project: The project to export
            settings: Export settings
            srt_path: Path to SRT file if subtitles should be burned
            
        Returns:
            Tuple of (command list, temporary files to clean up)
        """
        # Collect all clips sorted by timeline position
        video_clips = self._collect_video_clips(project)
        audio_clips = self._collect_audio_clips(project)
        
        if not video_clips:
            raise ValueError("No video clips to export")
        
        # Build command
        cmd = ["ffmpeg", "-y"]  # -y to overwrite output
        temp_files = []
        
        # Add inputs
        input_map = {}  # source_file -> input index
        input_idx = 0
        
        for clip in video_clips:
            if clip.source_file not in input_map:
                cmd.extend(["-i", clip.source_file])
                input_map[clip.source_file] = input_idx
                input_idx += 1
        
        for clip in audio_clips:
            if clip.source_file not in input_map:
                cmd.extend(["-i", clip.source_file])
                input_map[clip.source_file] = input_idx
                input_idx += 1
        
        # Build filter complex
        filter_parts = []
        concat_inputs = []
        
        # Process video clips
        for i, clip in enumerate(video_clips):
            input_i = input_map[clip.source_file]
            
            # Trim filter
            trim_label = f"v{i}"
            filter_parts.append(
                f"[{input_i}:v]trim=start={clip.in_time}:end={clip.out_time},"
                f"setpts=PTS-STARTPTS[{trim_label}]"
            )
            concat_inputs.append(f"[{trim_label}]")
        
        # Concatenate video clips
        if len(video_clips) > 1:
            filter_parts.append(
                f"{''.join(concat_inputs)}concat=n={len(video_clips)}:v=1:a=0[outv]"
            )
            video_output = "[outv]"
        else:
            video_output = concat_inputs[0] if concat_inputs else "[0:v]"
            # Rename single input to outv for consistency
            filter_parts.append(f"{video_output}null[outv]")
            video_output = "[outv]"
        
        # Process audio - for simplicity, use first video's audio
        # A more complete implementation would mix all audio tracks
        audio_concat_inputs = []
        for i, clip in enumerate(video_clips):
            input_i = input_map[clip.source_file]
            trim_label = f"a{i}"
            filter_parts.append(
                f"[{input_i}:a]atrim=start={clip.in_time}:end={clip.out_time},"
                f"asetpts=PTS-STARTPTS[{trim_label}]"
            )
            audio_concat_inputs.append(f"[{trim_label}]")
        
        if len(video_clips) > 1:
            filter_parts.append(
                f"{''.join(audio_concat_inputs)}concat=n={len(video_clips)}:v=0:a=1[outa]"
            )
            audio_output = "[outa]"
        else:
            audio_output = audio_concat_inputs[0] if audio_concat_inputs else "[0:a]"
            filter_parts.append(f"{audio_output}anull[outa]")
            audio_output = "[outa]"
        
        # Add scaling if needed
        final_video = video_output
        if settings.width or settings.height:
            filter_parts.append(
                f"[outv]scale={settings.width}:{settings.height}:force_original_aspect_ratio=decrease,"
                f"pad={settings.width}:{settings.height}:(ow-iw)/2:(oh-ih)/2[scaled]"
            )
            final_video = "[scaled]"
        
        # Add subtitle filter if SRT is provided
        if srt_path and settings.burn_subtitles and os.path.exists(srt_path):
            # Escape path for FFmpeg
            escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(
                f"{final_video}subtitles='{escaped_srt}':"
                f"force_style='FontSize=24,FontName=Arial,PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=30'[final]"
            )
            final_video = "[final]"
        else:
            # Rename to final for consistency
            filter_parts.append(f"{final_video}null[final]")
            final_video = "[final]"
        
        # Combine filter complex
        filter_complex = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_complex])
        
        # Map outputs
        cmd.extend([
            "-map", "[final]",
            "-map", "[outa]",
        ])
        
        # Encoding settings
        cmd.extend([
            "-c:v", settings.video_codec,
            "-preset", settings.video_preset,
            "-crf", str(settings.video_crf),
            "-c:a", settings.audio_codec,
            "-b:a", settings.audio_bitrate,
            "-r", str(settings.fps),
        ])
        
        # Output file
        cmd.append(settings.output_path)
        
        return cmd, temp_files
    
    def _collect_video_clips(self, project: "Project") -> List[TrimmedClip]:
        """Collect all video clips sorted by timeline position."""
        clips = []
        
        for track in project.video_tracks:
            for clip in track:
                if clip.enabled:
                    clips.append(TrimmedClip(
                        source_file=clip.source_file,
                        in_time=clip.in_time,
                        out_time=clip.out_time,
                        timeline_start=clip.timeline_start
                    ))
        
        # Sort by timeline position
        clips.sort(key=lambda c: c.timeline_start)
        return clips
    
    def _collect_audio_clips(self, project: "Project") -> List[TrimmedClip]:
        """Collect all audio clips."""
        clips = []
        
        for track in project.audio_tracks:
            for clip in track:
                if clip.enabled:
                    clips.append(TrimmedClip(
                        source_file=clip.source_file,
                        in_time=clip.in_time,
                        out_time=clip.out_time,
                        timeline_start=clip.timeline_start
                    ))
        
        clips.sort(key=lambda c: c.timeline_start)
        return clips
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)


def build_simple_concat_command(
    clips: List[Tuple[str, float, float]],  # (source, in, out)
    output_path: str,
    crf: int = 18
) -> List[str]:
    """
    Build a simple concatenation command without complex filtering.
    
    This is a fallback for simpler exports.
    
    Args:
        clips: List of (source_file, in_time, out_time) tuples
        output_path: Output file path
        crf: Video quality (lower = better, 18 = visually lossless)
        
    Returns:
        FFmpeg command as list of strings
    """
    cmd = ["ffmpeg", "-y"]
    
    filter_parts = []
    concat_inputs_v = []
    concat_inputs_a = []
    
    for i, (source, in_time, out_time) in enumerate(clips):
        cmd.extend(["-i", source])
        
        # Video trim
        filter_parts.append(
            f"[{i}:v]trim=start={in_time}:end={out_time},setpts=PTS-STARTPTS[v{i}]"
        )
        concat_inputs_v.append(f"[v{i}]")
        
        # Audio trim
        filter_parts.append(
            f"[{i}:a]atrim=start={in_time}:end={out_time},asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs_a.append(f"[a{i}]")
    
    # Concatenate
    n = len(clips)
    filter_parts.append(
        f"{''.join(concat_inputs_v)}concat=n={n}:v=1:a=0[outv]"
    )
    filter_parts.append(
        f"{''.join(concat_inputs_a)}concat=n={n}:v=0:a=1[outa]"
    )
    
    filter_complex = ";".join(filter_parts)
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ])
    
    return cmd
