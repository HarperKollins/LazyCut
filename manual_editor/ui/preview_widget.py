"""
Preview Widget

Video preview panel with playback controls.
Displays the current frame and provides transport controls.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QStyle, QSizePolicy,
    QFrame
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor

from manual_editor.playback.engine import PlaybackEngine


class PreviewWidget(QWidget):
    """
    Video preview panel with transport controls.
    
    Features:
    - Video frame display
    - Play/Pause button
    - Seek slider
    - Time display (current / total)
    
    Signals:
        position_changed: Emitted when user seeks (seconds)
    """
    
    position_changed = Signal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.engine = PlaybackEngine(self)
        self._duration = 0.0
        self._is_seeking = False
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video display area
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #333;
            }
        """)
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(320, 180)
        self.video_label.setStyleSheet("background-color: #000;")
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_layout.addWidget(self.video_label)
        
        layout.addWidget(self.video_frame, stretch=1)
        
        # Controls area
        controls_frame = QFrame()
        controls_frame.setFixedHeight(80)
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-top: 1px solid #444;
            }
        """)
        
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(10, 5, 10, 5)
        controls_layout.setSpacing(5)
        
        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #444;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4285f4;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #4285f4;
                border-radius: 3px;
            }
        """)
        controls_layout.addWidget(self.seek_slider)
        
        # Transport controls
        transport_layout = QHBoxLayout()
        transport_layout.setSpacing(10)
        
        # Time display (current)
        self.time_current = QLabel("00:00")
        self.time_current.setStyleSheet("color: #fff; font-family: monospace; font-size: 12px;")
        transport_layout.addWidget(self.time_current)
        
        transport_layout.addStretch()
        
        # Transport buttons
        btn_style = """
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """
        
        # Rewind button
        self.btn_rewind = QPushButton("⏮")
        self.btn_rewind.setFixedSize(36, 36)
        self.btn_rewind.setStyleSheet(btn_style)
        self.btn_rewind.clicked.connect(self._on_rewind)
        transport_layout.addWidget(self.btn_rewind)
        
        # Step back button
        self.btn_step_back = QPushButton("◀")
        self.btn_step_back.setFixedSize(36, 36)
        self.btn_step_back.setStyleSheet(btn_style)
        self.btn_step_back.clicked.connect(lambda: self.engine.seek_relative(-1.0))
        transport_layout.addWidget(self.btn_step_back)
        
        # Play/Pause button
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(48, 36)
        self.btn_play.setStyleSheet(btn_style + """
            QPushButton {
                background-color: #4285f4;
            }
            QPushButton:hover {
                background-color: #5294f5;
            }
        """)
        self.btn_play.clicked.connect(self._on_play_clicked)
        transport_layout.addWidget(self.btn_play)
        
        # Step forward button
        self.btn_step_forward = QPushButton("▶")
        self.btn_step_forward.setFixedSize(36, 36)
        self.btn_step_forward.setStyleSheet(btn_style)
        self.btn_step_forward.clicked.connect(lambda: self.engine.seek_relative(1.0))
        transport_layout.addWidget(self.btn_step_forward)
        
        # Forward button
        self.btn_forward = QPushButton("⏭")
        self.btn_forward.setFixedSize(36, 36)
        self.btn_forward.setStyleSheet(btn_style)
        self.btn_forward.clicked.connect(self._on_forward)
        transport_layout.addWidget(self.btn_forward)
        
        transport_layout.addStretch()
        
        # Time display (total)
        self.time_total = QLabel("00:00")
        self.time_total.setStyleSheet("color: #888; font-family: monospace; font-size: 12px;")
        transport_layout.addWidget(self.time_total)
        
        controls_layout.addLayout(transport_layout)
        layout.addWidget(controls_frame)
    
    def _connect_signals(self) -> None:
        """Connect engine signals."""
        self.engine.frame_ready.connect(self._on_frame_ready)
        self.engine.position_changed.connect(self._on_position_changed)
        self.engine.state_changed.connect(self._on_state_changed)
        self.engine.playback_finished.connect(self._on_playback_finished)
        
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)
    
    def set_source(self, video_path: str) -> bool:
        """Set the video source for preview."""
        success = self.engine.set_source(video_path)
        if success:
            self._duration = self.engine.duration
            self.time_total.setText(self._format_time(self._duration))
        return success
    
    def seek(self, time_seconds: float) -> None:
        """Seek to a specific time."""
        self.engine.seek(time_seconds)
    
    @Slot(QPixmap)
    def _on_frame_ready(self, pixmap: QPixmap) -> None:
        """Handle new frame from engine."""
        if pixmap.isNull():
            return
        
        # Scale pixmap to fit label while maintaining aspect ratio
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled)
    
    @Slot(float)
    def _on_position_changed(self, seconds: float) -> None:
        """Handle position update from engine."""
        self.time_current.setText(self._format_time(seconds))
        
        if not self._is_seeking and self._duration > 0:
            slider_value = int((seconds / self._duration) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(slider_value)
            self.seek_slider.blockSignals(False)
        
        self.position_changed.emit(seconds)
    
    @Slot(bool)
    def _on_state_changed(self, is_playing: bool) -> None:
        """Handle play state change."""
        self.btn_play.setText("⏸" if is_playing else "▶")
    
    @Slot()
    def _on_playback_finished(self) -> None:
        """Handle playback reaching end."""
        pass
    
    def _on_play_clicked(self) -> None:
        """Handle play button click."""
        self.engine.toggle_playback()
    
    def _on_rewind(self) -> None:
        """Go to beginning."""
        self.engine.seek(0)
    
    def _on_forward(self) -> None:
        """Go to end."""
        self.engine.seek(self._duration)
    
    def _on_slider_pressed(self) -> None:
        """Handle slider press - pause for seeking."""
        self._is_seeking = True
        self._was_playing = self.engine.is_playing
        self.engine.pause()
    
    def _on_slider_released(self) -> None:
        """Handle slider release - resume if was playing."""
        self._is_seeking = False
        if self._was_playing:
            self.engine.play()
    
    def _on_slider_moved(self, value: int) -> None:
        """Handle slider drag."""
        if self._duration > 0:
            time = (value / 1000.0) * self._duration
            self.engine.seek(time)
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def resizeEvent(self, event):
        """Handle resize to update video scaling."""
        super().resizeEvent(event)
        # Re-emit current frame at new size
        if hasattr(self, 'engine') and self.engine.current_time >= 0:
            self.engine._decode_and_emit_current_frame()
