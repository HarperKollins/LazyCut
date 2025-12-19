"""
Project Data Model

This module defines the core data structures for the Manual Video Editor.
All timeline operations modify these data structures, which are then
rendered by the UI and used by the export pipeline.

The data model follows a time-based approach where:
- Clips reference source files and define in/out points
- Timeline positions are stored in seconds
- The actual video files are never modified

Architecture:
    Project
    ├── video_tracks: List[List[Clip]]
    ├── audio_tracks: List[List[AudioClip]]
    ├── subtitles: List[Subtitle]
    └── settings: ProjectSettings
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import uuid
import os


@dataclass
class Clip:
    """
    Represents a video clip on the timeline.
    
    A clip is a reference to a portion of a source video file,
    placed at a specific position on the timeline.
    
    Attributes:
        id: Unique identifier for this clip
        source_file: Absolute path to the source video file
        in_time: Start time in the source file (seconds)
        out_time: End time in the source file (seconds)
        timeline_start: Position on the timeline where this clip starts (seconds)
        track_index: Which video track this clip is on (0-indexed)
        name: Display name for the clip (defaults to filename)
        enabled: Whether this clip is included in playback/export
    """
    id: str
    source_file: str
    in_time: float
    out_time: float
    timeline_start: float
    track_index: int = 0
    name: str = ""
    enabled: bool = True
    
    def __post_init__(self):
        if not self.name:
            self.name = os.path.basename(self.source_file)
    
    @property
    def duration(self) -> float:
        """Duration of this clip on the timeline."""
        return self.out_time - self.in_time
    
    @property
    def timeline_end(self) -> float:
        """End position on the timeline."""
        return self.timeline_start + self.duration
    
    def contains_time(self, time: float) -> bool:
        """Check if a timeline time falls within this clip."""
        return self.timeline_start <= time < self.timeline_end
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "source_file": self.source_file,
            "in_time": self.in_time,
            "out_time": self.out_time,
            "timeline_start": self.timeline_start,
            "track_index": self.track_index,
            "name": self.name,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clip":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            source_file=data["source_file"],
            in_time=data["in_time"],
            out_time=data["out_time"],
            timeline_start=data["timeline_start"],
            track_index=data.get("track_index", 0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True)
        )
    
    @staticmethod
    def create_new(
        source_file: str,
        in_time: float,
        out_time: float,
        timeline_start: float,
        track_index: int = 0
    ) -> "Clip":
        """Factory method to create a new clip with a generated ID."""
        return Clip(
            id=str(uuid.uuid4()),
            source_file=source_file,
            in_time=in_time,
            out_time=out_time,
            timeline_start=timeline_start,
            track_index=track_index
        )


@dataclass
class AudioClip:
    """
    Represents an audio clip on the timeline.
    
    Similar to Clip but for audio-only files (music, voiceover, etc.)
    
    Attributes:
        id: Unique identifier
        source_file: Path to audio file (mp3, wav, etc.)
        in_time: Start time in source file (seconds)
        out_time: End time in source file (seconds)
        timeline_start: Position on timeline (seconds)
        track_index: Which audio track (0 = primary audio, 1+ = additional)
        volume: Volume multiplier (0.0 to 2.0, default 1.0)
        name: Display name
        enabled: Whether included in export
    """
    id: str
    source_file: str
    in_time: float
    out_time: float
    timeline_start: float
    track_index: int = 0
    volume: float = 1.0
    name: str = ""
    enabled: bool = True
    
    def __post_init__(self):
        if not self.name:
            self.name = os.path.basename(self.source_file)
    
    @property
    def duration(self) -> float:
        return self.out_time - self.in_time
    
    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_file": self.source_file,
            "in_time": self.in_time,
            "out_time": self.out_time,
            "timeline_start": self.timeline_start,
            "track_index": self.track_index,
            "volume": self.volume,
            "name": self.name,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioClip":
        return cls(
            id=data["id"],
            source_file=data["source_file"],
            in_time=data["in_time"],
            out_time=data["out_time"],
            timeline_start=data["timeline_start"],
            track_index=data.get("track_index", 0),
            volume=data.get("volume", 1.0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True)
        )
    
    @staticmethod
    def create_new(
        source_file: str,
        in_time: float,
        out_time: float,
        timeline_start: float,
        track_index: int = 0,
        volume: float = 1.0
    ) -> "AudioClip":
        return AudioClip(
            id=str(uuid.uuid4()),
            source_file=source_file,
            in_time=in_time,
            out_time=out_time,
            timeline_start=timeline_start,
            track_index=track_index,
            volume=volume
        )


@dataclass
class Subtitle:
    """
    Represents a subtitle/text overlay.
    
    Subtitles are burned into the final video during export.
    
    Attributes:
        id: Unique identifier
        text: The subtitle text content
        start_time: When the subtitle appears on timeline (seconds)
        duration: How long the subtitle is visible (seconds)
        style: Font styling options
    """
    id: str
    text: str
    start_time: float
    duration: float
    style: Dict[str, Any] = field(default_factory=lambda: {
        "font_name": "Arial",
        "font_size": 24,
        "font_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "position": "bottom",  # top, center, bottom
        "alignment": "center"  # left, center, right
    })
    
    @property
    def end_time(self) -> float:
        return self.start_time + self.duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "start_time": self.start_time,
            "duration": self.duration,
            "style": self.style.copy()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtitle":
        return cls(
            id=data["id"],
            text=data["text"],
            start_time=data["start_time"],
            duration=data["duration"],
            style=data.get("style", {})
        )
    
    @staticmethod
    def create_new(
        text: str,
        start_time: float,
        duration: float = 3.0
    ) -> "Subtitle":
        return Subtitle(
            id=str(uuid.uuid4()),
            text=text,
            start_time=start_time,
            duration=duration
        )


@dataclass
class ProjectSettings:
    """
    Project-wide settings.
    
    Attributes:
        width: Output video width
        height: Output video height
        fps: Output frame rate
        sample_rate: Audio sample rate
    """
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    sample_rate: int = 48000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "sample_rate": self.sample_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectSettings":
        return cls(
            width=data.get("width", 1920),
            height=data.get("height", 1080),
            fps=data.get("fps", 30.0),
            sample_rate=data.get("sample_rate", 48000)
        )


class Project:
    """
    The main project container.
    
    Holds all clips, audio, subtitles, and settings for a video project.
    This is the single source of truth for the timeline state.
    
    The project supports multiple video and audio tracks:
    - video_tracks[0] = Main video track
    - audio_tracks[0] = Primary audio (from video)
    - audio_tracks[1] = Music track
    - audio_tracks[2+] = Additional audio
    """
    
    def __init__(self, name: str = "Untitled Project"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.file_path: Optional[str] = None  # Where project is saved
        
        # Initialize with 1 video track and 2 audio tracks
        self.video_tracks: List[List[Clip]] = [[]]
        self.audio_tracks: List[List[AudioClip]] = [[], []]
        self.subtitles: List[Subtitle] = []
        self.settings = ProjectSettings()
        
        # Media pool - imported files available for use
        self.media_pool: List[str] = []
    
    @property
    def duration(self) -> float:
        """
        Calculate the total duration of the timeline.
        This is the end time of the last clip/audio/subtitle.
        """
        max_time = 0.0
        
        for track in self.video_tracks:
            for clip in track:
                if clip.enabled:
                    max_time = max(max_time, clip.timeline_end)
        
        for track in self.audio_tracks:
            for clip in track:
                if clip.enabled:
                    max_time = max(max_time, clip.timeline_end)
        
        for sub in self.subtitles:
            max_time = max(max_time, sub.end_time)
        
        return max_time
    
    def get_clip_by_id(self, clip_id: str) -> Optional[Clip]:
        """Find a clip by its ID across all video tracks."""
        for track in self.video_tracks:
            for clip in track:
                if clip.id == clip_id:
                    return clip
        return None
    
    def get_audio_clip_by_id(self, clip_id: str) -> Optional[AudioClip]:
        """Find an audio clip by its ID across all audio tracks."""
        for track in self.audio_tracks:
            for clip in track:
                if clip.id == clip_id:
                    return clip
        return None
    
    def get_subtitle_by_id(self, sub_id: str) -> Optional[Subtitle]:
        """Find a subtitle by its ID."""
        for sub in self.subtitles:
            if sub.id == sub_id:
                return sub
        return None
    
    def add_clip(self, clip: Clip) -> None:
        """Add a clip to the appropriate video track."""
        while len(self.video_tracks) <= clip.track_index:
            self.video_tracks.append([])
        self.video_tracks[clip.track_index].append(clip)
    
    def add_audio_clip(self, clip: AudioClip) -> None:
        """Add an audio clip to the appropriate audio track."""
        while len(self.audio_tracks) <= clip.track_index:
            self.audio_tracks.append([])
        self.audio_tracks[clip.track_index].append(clip)
    
    def add_subtitle(self, subtitle: Subtitle) -> None:
        """Add a subtitle to the project."""
        self.subtitles.append(subtitle)
    
    def remove_clip(self, clip_id: str) -> bool:
        """Remove a clip by ID. Returns True if found and removed."""
        for track in self.video_tracks:
            for i, clip in enumerate(track):
                if clip.id == clip_id:
                    track.pop(i)
                    return True
        return False
    
    def remove_audio_clip(self, clip_id: str) -> bool:
        """Remove an audio clip by ID."""
        for track in self.audio_tracks:
            for i, clip in enumerate(track):
                if clip.id == clip_id:
                    track.pop(i)
                    return True
        return False
    
    def remove_subtitle(self, sub_id: str) -> bool:
        """Remove a subtitle by ID."""
        for i, sub in enumerate(self.subtitles):
            if sub.id == sub_id:
                self.subtitles.pop(i)
                return True
        return False
    
    def get_clips_at_time(self, time: float) -> List[Clip]:
        """Get all video clips that are active at a specific time."""
        clips = []
        for track in self.video_tracks:
            for clip in track:
                if clip.enabled and clip.contains_time(time):
                    clips.append(clip)
        return clips
    
    def get_all_clips(self) -> List[Clip]:
        """Get all video clips from all tracks."""
        clips = []
        for track in self.video_tracks:
            clips.extend(track)
        return clips
    
    def get_all_audio_clips(self) -> List[AudioClip]:
        """Get all audio clips from all tracks."""
        clips = []
        for track in self.audio_tracks:
            clips.extend(track)
        return clips
    
    def import_media(self, file_path: str) -> bool:
        """Add a file to the media pool."""
        if os.path.exists(file_path) and file_path not in self.media_pool:
            self.media_pool.append(file_path)
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the project to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "video_tracks": [
                [clip.to_dict() for clip in track]
                for track in self.video_tracks
            ],
            "audio_tracks": [
                [clip.to_dict() for clip in track]
                for track in self.audio_tracks
            ],
            "subtitles": [sub.to_dict() for sub in self.subtitles],
            "settings": self.settings.to_dict(),
            "media_pool": self.media_pool.copy()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Deserialize a project from a dictionary."""
        project = cls(name=data.get("name", "Untitled"))
        project.id = data.get("id", str(uuid.uuid4()))
        
        project.video_tracks = [
            [Clip.from_dict(clip_data) for clip_data in track]
            for track in data.get("video_tracks", [[]])
        ]
        
        project.audio_tracks = [
            [AudioClip.from_dict(clip_data) for clip_data in track]
            for track in data.get("audio_tracks", [[], []])
        ]
        
        project.subtitles = [
            Subtitle.from_dict(sub_data)
            for sub_data in data.get("subtitles", [])
        ]
        
        if "settings" in data:
            project.settings = ProjectSettings.from_dict(data["settings"])
        
        project.media_pool = data.get("media_pool", [])
        
        return project
    
    def __repr__(self) -> str:
        return (
            f"Project(name='{self.name}', "
            f"clips={len(self.get_all_clips())}, "
            f"audio={len(self.get_all_audio_clips())}, "
            f"subtitles={len(self.subtitles)}, "
            f"duration={self.duration:.2f}s)"
        )
