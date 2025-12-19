"""
Playback Engine

Handles video playback for the preview panel. Uses FFmpeg to extract
frames and a timer-based approach for playback synchronization.

The engine operates on proxy files for smooth playback regardless
of source video resolution.

Architecture:
    PlaybackEngine
    ├── Frame decoder (FFmpeg subprocess)
    ├── Frame buffer (pre-decoded frames)
    ├── Playback timer (QTimer)
    └── Position tracking
"""

import os
import subprocess
import tempfile
import threading
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from queue import Queue, Empty

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap

# Local imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from shared.ffmpeg_utils import get_ffmpeg_path, get_video_metadata


@dataclass
class PlaybackFrame:
    """Container for a decoded frame."""
    time: float          # Time in seconds
    image: QImage        # Decoded image
    source_file: str     # Source video path


class FrameDecoder:
    """
    Decodes video frames using FFmpeg.
    
    Uses a subprocess to pipe raw RGB data, which is then
    converted to QImage for display.
    """
    
    def __init__(self, video_path: str, width: int = 640, height: int = 360):
        self.video_path = video_path
        self.width = width
        self.height = height
        self._process: Optional[subprocess.Popen] = None
        self._metadata = None
        
        try:
            self._metadata = get_video_metadata(video_path)
            # Calculate height maintaining aspect ratio
            aspect = self._metadata.width / self._metadata.height
            self.height = int(self.width / aspect)
            # Ensure even dimensions
            self.width = self.width - (self.width % 2)
            self.height = self.height - (self.height % 2)
        except Exception:
            pass
    
    def decode_frame(self, time_seconds: float) -> Optional[QImage]:
        """
        Decode a single frame at the specified time.
        
        Args:
            time_seconds: Time position to extract frame from
            
        Returns:
            QImage or None if decoding fails
        """
        ffmpeg = get_ffmpeg_path()
        
        cmd = [
            ffmpeg,
            "-ss", str(time_seconds),
            "-i", self.video_path,
            "-vframes", "1",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5.0,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            
            if result.returncode == 0 and result.stdout:
                # Convert raw RGB to QImage
                expected_size = self.width * self.height * 3
                if len(result.stdout) >= expected_size:
                    image = QImage(
                        result.stdout[:expected_size],
                        self.width,
                        self.height,
                        self.width * 3,
                        QImage.Format_RGB888
                    )
                    return image.copy()  # Make a copy since buffer will be freed
            
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        
        return None
    
    @property
    def duration(self) -> float:
        """Get video duration in seconds."""
        if self._metadata:
            return self._metadata.duration
        return 0.0
    
    @property
    def fps(self) -> float:
        """Get video frame rate."""
        if self._metadata:
            return self._metadata.fps
        return 30.0


class PlaybackEngine(QObject):
    """
    Main playback controller.
    
    Manages frame decoding, timing, and playback state.
    Emits signals for UI updates.
    
    Signals:
        frame_ready: Emitted when a new frame is ready (QPixmap)
        position_changed: Emitted when playback position changes (seconds)
        playback_finished: Emitted when playback reaches end
        state_changed: Emitted when play/pause state changes (is_playing)
    """
    
    frame_ready = Signal(QPixmap)
    position_changed = Signal(float)
    playback_finished = Signal()
    state_changed = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self._is_playing = False
        self._current_time = 0.0
        self._duration = 0.0
        
        # Current source
        self._current_source: Optional[str] = None
        self._decoder: Optional[FrameDecoder] = None
        
        # Playback timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._frame_interval = 33  # ~30 fps
        
        # Frame cache for smoother scrubbing
        self._frame_cache: dict = {}
        self._cache_max_size = 100
    
    def set_source(self, video_path: str) -> bool:
        """
        Set the video source for playback.
        
        Args:
            video_path: Path to video file
            
        Returns:
            True if source was loaded successfully
        """
        if not os.path.exists(video_path):
            return False
        
        self.stop()
        
        self._current_source = video_path
        self._decoder = FrameDecoder(video_path)
        self._duration = self._decoder.duration
        self._current_time = 0.0
        
        # Update frame interval based on source fps
        fps = self._decoder.fps
        self._frame_interval = int(1000 / min(fps, 30))  # Cap at 30 fps for preview
        
        # Decode and emit first frame
        self._decode_and_emit_current_frame()
        
        return True
    
    def play(self) -> None:
        """Start playback."""
        if not self._decoder:
            return
        
        if self._current_time >= self._duration:
            self._current_time = 0.0
        
        self._is_playing = True
        self._timer.start(self._frame_interval)
        self.state_changed.emit(True)
    
    def pause(self) -> None:
        """Pause playback."""
        self._is_playing = False
        self._timer.stop()
        self.state_changed.emit(False)
    
    def toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self._is_playing:
            self.pause()
        else:
            self.play()
    
    def stop(self) -> None:
        """Stop playback and reset to beginning."""
        self.pause()
        self._current_time = 0.0
        self.position_changed.emit(0.0)
        
        if self._decoder:
            self._decode_and_emit_current_frame()
    
    def seek(self, time_seconds: float) -> None:
        """
        Seek to a specific time position.
        
        Args:
            time_seconds: Target time in seconds
        """
        if not self._decoder:
            return
        
        self._current_time = max(0, min(time_seconds, self._duration))
        self.position_changed.emit(self._current_time)
        self._decode_and_emit_current_frame()
    
    def seek_relative(self, delta_seconds: float) -> None:
        """Seek relative to current position."""
        self.seek(self._current_time + delta_seconds)
    
    @property
    def is_playing(self) -> bool:
        """Whether playback is currently active."""
        return self._is_playing
    
    @property
    def current_time(self) -> float:
        """Current playback position in seconds."""
        return self._current_time
    
    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        return self._duration
    
    def _on_timer_tick(self) -> None:
        """Called on each timer tick during playback."""
        if not self._is_playing:
            return
        
        # Advance time
        self._current_time += self._frame_interval / 1000.0
        
        if self._current_time >= self._duration:
            self._current_time = self._duration
            self.pause()
            self.playback_finished.emit()
            return
        
        self.position_changed.emit(self._current_time)
        self._decode_and_emit_current_frame()
    
    def _decode_and_emit_current_frame(self) -> None:
        """Decode the frame at current time and emit signal."""
        if not self._decoder:
            return
        
        # Check cache first
        cache_key = f"{self._current_source}:{self._current_time:.2f}"
        if cache_key in self._frame_cache:
            pixmap = self._frame_cache[cache_key]
            self.frame_ready.emit(pixmap)
            return
        
        # Decode frame
        image = self._decoder.decode_frame(self._current_time)
        if image:
            pixmap = QPixmap.fromImage(image)
            
            # Add to cache
            if len(self._frame_cache) >= self._cache_max_size:
                # Remove oldest entries
                keys = list(self._frame_cache.keys())
                for key in keys[:10]:
                    del self._frame_cache[key]
            
            self._frame_cache[cache_key] = pixmap
            self.frame_ready.emit(pixmap)
