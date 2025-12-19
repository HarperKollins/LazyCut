"""
Timeline Widget

The main timeline component using QGraphicsView/QGraphicsScene architecture.
This provides the core editing interface for the Manual Video Editor.

Architecture:
    TimelineWidget (QWidget)
    ├── TimelineView (QGraphicsView)
    │   └── TimelineScene (QGraphicsScene)
    │       ├── TimelineRuler
    │       ├── TrackHeader (multiple)
    │       ├── TimelineClipItem (multiple)
    │       └── PlayheadItem
    └── Controls (zoom slider, etc.)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, 
    QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QSlider, QLabel, QPushButton,
    QGraphicsItem, QMenu, QScrollBar
)
from PySide6.QtCore import (
    Qt, Signal, QRectF, QPointF, QLineF, QTimer
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QWheelEvent,
    QMouseEvent, QKeyEvent, QTransform
)
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from manual_editor.models.project import Project, Clip, AudioClip


# ============================================================================
# Constants
# ============================================================================

# Timeline dimensions
RULER_HEIGHT = 30
TRACK_HEIGHT = 60
TRACK_HEADER_WIDTH = 100
TRACK_SPACING = 2

# Colors
COLOR_BACKGROUND = QColor(30, 30, 35)
COLOR_RULER = QColor(45, 45, 50)
COLOR_RULER_TEXT = QColor(180, 180, 180)
COLOR_TRACK_BG = QColor(40, 40, 45)
COLOR_TRACK_HEADER = QColor(50, 50, 55)
COLOR_VIDEO_CLIP = QColor(66, 133, 244)  # Blue
COLOR_VIDEO_CLIP_SELECTED = QColor(100, 160, 255)
COLOR_AUDIO_CLIP = QColor(52, 168, 83)   # Green
COLOR_AUDIO_CLIP_SELECTED = QColor(80, 200, 110)
COLOR_PLAYHEAD = QColor(255, 80, 80)     # Red
COLOR_SELECTION = QColor(255, 255, 255, 50)


class TimelineClipItem(QGraphicsRectItem):
    """
    Graphical representation of a video or audio clip on the timeline.
    
    Features:
    - Draggable horizontally
    - Edge handles for trimming
    - Selection highlighting
    - Context menu
    """
    
    def __init__(
        self,
        clip_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        name: str,
        is_audio: bool = False,
        parent=None
    ):
        super().__init__(x, y, width, height, parent)
        
        self.clip_id = clip_id
        self.clip_name = name
        self.is_audio = is_audio
        self._is_selected = False
        self._is_trimming_left = False
        self._is_trimming_right = False
        self._drag_start_x: Optional[float] = None
        self._original_x: Optional[float] = None
        self._original_width: Optional[float] = None
        self._trim_handle_width = 8  # Pixels for trim handle zones
        
        # Enable interactions
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set appearance
        self._update_appearance()
        
        # Add name label
        self._label = QGraphicsTextItem(self)
        self._label.setPlainText(self._truncate_name(name, width))
        self._label.setDefaultTextColor(Qt.white)
        font = QFont("Arial", 9)
        self._label.setFont(font)
        self._label.setPos(x + 4, y + 2)
    
    def _truncate_name(self, name: str, width: float) -> str:
        """Truncate name to fit in clip rectangle."""
        max_chars = int(width / 7)  # Approximate character width
        if len(name) > max_chars and max_chars > 3:
            return name[:max_chars - 3] + "..."
        return name if len(name) <= max_chars else ""
    
    def _update_appearance(self) -> None:
        """Update visual appearance based on state."""
        if self.is_audio:
            color = COLOR_AUDIO_CLIP_SELECTED if self._is_selected else COLOR_AUDIO_CLIP
        else:
            color = COLOR_VIDEO_CLIP_SELECTED if self._is_selected else COLOR_VIDEO_CLIP
        
        self.setBrush(QBrush(color))
        pen = QPen(color.lighter(130) if self._is_selected else color.darker(110))
        pen.setWidth(2 if self._is_selected else 1)
        self.setPen(pen)
    
    def setSelected(self, selected: bool) -> None:
        """Override to update appearance on selection change."""
        self._is_selected = selected
        super().setSelected(selected)
        self._update_appearance()
    
    def paint(self, painter, option, widget=None):
        """Custom paint with trim handles indication."""
        super().paint(painter, option, widget)
        
        # Draw trim handles when selected
        if self._is_selected:
            rect = self.rect()
            handle_color = QColor(255, 255, 255, 100)
            painter.setBrush(QBrush(handle_color))
            painter.setPen(Qt.NoPen)
            
            # Left handle
            painter.drawRect(
                rect.x(), rect.y(),
                self._trim_handle_width, rect.height()
            )
            
            # Right handle
            painter.drawRect(
                rect.x() + rect.width() - self._trim_handle_width,
                rect.y(),
                self._trim_handle_width, rect.height()
            )
    
    def hoverMoveEvent(self, event):
        """Change cursor based on position for trim handles."""
        pos = event.pos()
        rect = self.rect()
        
        if pos.x() < rect.x() + self._trim_handle_width:
            self.setCursor(Qt.SizeHorCursor)
        elif pos.x() > rect.x() + rect.width() - self._trim_handle_width:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        super().hoverMoveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press for selection and dragging."""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            rect = self.rect()
            
            self._drag_start_x = event.scenePos().x()
            self._original_x = rect.x()
            self._original_width = rect.width()
            
            # Check if clicking on trim handles
            if pos.x() < rect.x() + self._trim_handle_width:
                self._is_trimming_left = True
            elif pos.x() > rect.x() + rect.width() - self._trim_handle_width:
                self._is_trimming_right = True
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle dragging and trimming."""
        if self._drag_start_x is not None:
            delta_x = event.scenePos().x() - self._drag_start_x
            
            if self._is_trimming_left:
                # Trim left edge - adjust x and width
                new_x = max(0, self._original_x + delta_x)
                new_width = self._original_width - (new_x - self._original_x)
                if new_width > 20:  # Minimum clip width
                    rect = self.rect()
                    self.setRect(new_x, rect.y(), new_width, rect.height())
            elif self._is_trimming_right:
                # Trim right edge - adjust width only
                new_width = max(20, self._original_width + delta_x)
                rect = self.rect()
                self.setRect(rect.x(), rect.y(), new_width, rect.height())
            else:
                # Normal drag - use default behavior but constrain to track
                super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Clean up after drag/trim."""
        self._is_trimming_left = False
        self._is_trimming_right = False
        self._drag_start_x = None
        super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event):
        """Show context menu."""
        menu = QMenu()
        
        split_action = menu.addAction("Split at Playhead")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        properties_action = menu.addAction("Properties...")
        
        action = menu.exec_(event.screenPos())
        
        if action == delete_action:
            # Emit signal through scene/view
            if self.scene():
                self.scene().views()[0].clip_deleted.emit(self.clip_id)
        elif action == split_action:
            if self.scene():
                self.scene().views()[0].clip_split_requested.emit(self.clip_id)


class PlayheadItem(QGraphicsLineItem):
    """
    The playhead indicator - a vertical line showing current time position.
    """
    
    def __init__(self, x: float, height: float, parent=None):
        super().__init__(x, 0, x, height, parent)
        
        self._height = height
        
        # Appearance
        pen = QPen(COLOR_PLAYHEAD)
        pen.setWidth(2)
        self.setPen(pen)
        
        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeHorCursor)
    
    def set_position(self, x: float) -> None:
        """Set the playhead position."""
        self.setLine(x, 0, x, self._height)
    
    def set_height(self, height: float) -> None:
        """Update the playhead height."""
        self._height = height
        line = self.line()
        self.setLine(line.x1(), 0, line.x1(), height)
    
    def get_x_position(self) -> float:
        """Get current x position."""
        return self.line().x1()
    
    def mouseMoveEvent(self, event):
        """Constrain movement to horizontal only."""
        new_x = event.scenePos().x()
        new_x = max(0, new_x)  # Don't go negative
        self.set_position(new_x)


class TimelineRuler(QGraphicsRectItem):
    """
    The time ruler showing time markers and labels.
    """
    
    def __init__(self, width: float, height: float, pixels_per_second: float):
        super().__init__(0, 0, width, height)
        
        self.pixels_per_second = pixels_per_second
        self._width = width
        
        self.setBrush(QBrush(COLOR_RULER))
        self.setPen(QPen(Qt.NoPen))
    
    def paint(self, painter, option, widget=None):
        """Custom paint to draw time markers."""
        super().paint(painter, option, widget)
        
        painter.setPen(QPen(COLOR_RULER_TEXT))
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        # Determine tick interval based on zoom level
        if self.pixels_per_second >= 100:
            major_interval = 1  # Every second
            minor_interval = 0.1
        elif self.pixels_per_second >= 30:
            major_interval = 5  # Every 5 seconds
            minor_interval = 1
        elif self.pixels_per_second >= 10:
            major_interval = 10  # Every 10 seconds
            minor_interval = 5
        else:
            major_interval = 30  # Every 30 seconds
            minor_interval = 10
        
        # Draw ticks
        time = 0
        while time * self.pixels_per_second < self._width:
            x = time * self.pixels_per_second
            
            if time % major_interval == 0:
                # Major tick with label
                painter.drawLine(int(x), int(RULER_HEIGHT - 15), int(x), int(RULER_HEIGHT))
                label = self._format_time(time)
                painter.drawText(int(x + 3), int(RULER_HEIGHT - 18), label)
            else:
                # Minor tick
                painter.drawLine(int(x), int(RULER_HEIGHT - 8), int(x), int(RULER_HEIGHT))
            
            time += minor_interval
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def set_pixels_per_second(self, pps: float) -> None:
        """Update zoom level."""
        self.pixels_per_second = pps
        self.update()
    
    def set_width(self, width: float) -> None:
        """Update ruler width."""
        self._width = width
        self.setRect(0, 0, width, RULER_HEIGHT)


class TrackHeader(QGraphicsRectItem):
    """
    Header for a track showing track name and controls.
    """
    
    def __init__(self, y: float, name: str, track_type: str = "video"):
        super().__init__(0, y, TRACK_HEADER_WIDTH, TRACK_HEIGHT)
        
        self.track_name = name
        self.track_type = track_type
        
        self.setBrush(QBrush(COLOR_TRACK_HEADER))
        self.setPen(QPen(Qt.NoPen))
        
        # Add label
        self._label = QGraphicsTextItem(self)
        self._label.setPlainText(name)
        self._label.setDefaultTextColor(Qt.white)
        font = QFont("Arial", 9, QFont.Bold)
        self._label.setFont(font)
        self._label.setPos(5, y + 5)


class TimelineScene(QGraphicsScene):
    """
    The scene containing all timeline elements.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setBackgroundBrush(QBrush(COLOR_BACKGROUND))


class TimelineView(QGraphicsView):
    """
    The main view for the timeline scene.
    
    Signals:
        time_changed: Emitted when playhead moves (time in seconds)
        clip_selected: Emitted when a clip is selected (clip_id)
        clip_moved: Emitted when a clip is moved (clip_id, new_start_seconds)
        clip_trimmed: Emitted when a clip is trimmed (clip_id, new_in, new_out, new_start)
        clip_deleted: Emitted when a clip should be deleted (clip_id)
        clip_split_requested: Emitted when split is requested (clip_id)
    """
    
    # Signals
    time_changed = Signal(float)
    clip_selected = Signal(str)
    clip_moved = Signal(str, float)
    clip_trimmed = Signal(str, float, float, float)
    clip_deleted = Signal(str)
    clip_split_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._scene = TimelineScene(self)
        self.setScene(self._scene)
        
        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Timeline state
        self.pixels_per_second = 50.0  # Zoom level
        self.project: Optional["Project"] = None
        
        # Scene elements
        self._ruler: Optional[TimelineRuler] = None
        self._playhead: Optional[PlayheadItem] = None
        self._clip_items: Dict[str, TimelineClipItem] = {}
        self._track_headers: List[TrackHeader] = []
        
        # Initialize
        self._init_scene()
    
    def _init_scene(self) -> None:
        """Initialize the scene with basic elements."""
        # Create ruler
        self._ruler = TimelineRuler(2000, RULER_HEIGHT, self.pixels_per_second)
        self._scene.addItem(self._ruler)
        
        # Create playhead
        total_height = RULER_HEIGHT + TRACK_HEIGHT * 3  # Default 3 tracks
        self._playhead = PlayheadItem(0, total_height)
        self._scene.addItem(self._playhead)
        
        # Set scene rect
        self._scene.setSceneRect(0, 0, 2000, total_height)
    
    def set_project(self, project: "Project") -> None:
        """Load a project into the timeline."""
        self.project = project
        self.refresh_timeline()
    
    def refresh_timeline(self) -> None:
        """Rebuild the timeline from the current project."""
        if not self.project:
            return
        
        # Clear existing clips
        for clip_id in list(self._clip_items.keys()):
            item = self._clip_items.pop(clip_id)
            self._scene.removeItem(item)
        
        # Clear track headers
        for header in self._track_headers:
            self._scene.removeItem(header)
        self._track_headers.clear()
        
        # Calculate total tracks
        num_video_tracks = len(self.project.video_tracks)
        num_audio_tracks = len(self.project.audio_tracks)
        if num_video_tracks == 0:
            num_video_tracks = 1
        if num_audio_tracks == 0:
            num_audio_tracks = 2
        
        total_tracks = num_video_tracks + num_audio_tracks
        
        # Calculate dimensions
        track_area_start = RULER_HEIGHT
        total_height = RULER_HEIGHT + (TRACK_HEIGHT + TRACK_SPACING) * total_tracks
        timeline_width = max(2000, self.project.duration * self.pixels_per_second + 500)
        
        # Update ruler
        self._ruler.set_width(timeline_width)
        self._ruler.set_pixels_per_second(self.pixels_per_second)
        
        # Create track headers and backgrounds
        y = track_area_start
        
        # Video tracks
        for i in range(num_video_tracks):
            header = TrackHeader(y, f"Video {i + 1}", "video")
            self._scene.addItem(header)
            self._track_headers.append(header)
            
            # Track background
            bg = QGraphicsRectItem(TRACK_HEADER_WIDTH, y, timeline_width, TRACK_HEIGHT)
            bg.setBrush(QBrush(COLOR_TRACK_BG))
            bg.setPen(QPen(Qt.NoPen))
            bg.setZValue(-1)
            self._scene.addItem(bg)
            
            y += TRACK_HEIGHT + TRACK_SPACING
        
        # Audio tracks
        for i in range(num_audio_tracks):
            header = TrackHeader(y, f"Audio {i + 1}", "audio")
            self._scene.addItem(header)
            self._track_headers.append(header)
            
            # Track background
            bg = QGraphicsRectItem(TRACK_HEADER_WIDTH, y, timeline_width, TRACK_HEIGHT)
            bg.setBrush(QBrush(COLOR_TRACK_BG.darker(110)))
            bg.setPen(QPen(Qt.NoPen))
            bg.setZValue(-1)
            self._scene.addItem(bg)
            
            y += TRACK_HEIGHT + TRACK_SPACING
        
        # Add video clips
        for track_idx, track in enumerate(self.project.video_tracks):
            track_y = track_area_start + track_idx * (TRACK_HEIGHT + TRACK_SPACING)
            
            for clip in track:
                if not clip.enabled:
                    continue
                
                x = TRACK_HEADER_WIDTH + clip.timeline_start * self.pixels_per_second
                width = clip.duration * self.pixels_per_second
                
                item = TimelineClipItem(
                    clip_id=clip.id,
                    x=x,
                    y=track_y,
                    width=width,
                    height=TRACK_HEIGHT - 4,
                    name=clip.name,
                    is_audio=False
                )
                self._scene.addItem(item)
                self._clip_items[clip.id] = item
        
        # Add audio clips
        for track_idx, track in enumerate(self.project.audio_tracks):
            track_y = track_area_start + (num_video_tracks + track_idx) * (TRACK_HEIGHT + TRACK_SPACING)
            
            for clip in track:
                if not clip.enabled:
                    continue
                
                x = TRACK_HEADER_WIDTH + clip.timeline_start * self.pixels_per_second
                width = clip.duration * self.pixels_per_second
                
                item = TimelineClipItem(
                    clip_id=clip.id,
                    x=x,
                    y=track_y,
                    width=width,
                    height=TRACK_HEIGHT - 4,
                    name=clip.name,
                    is_audio=True
                )
                self._scene.addItem(item)
                self._clip_items[clip.id] = item
        
        # Update playhead height
        if self._playhead:
            self._playhead.set_height(total_height)
        
        # Update scene rect
        self._scene.setSceneRect(0, 0, timeline_width, total_height)
    
    def set_playhead_time(self, seconds: float) -> None:
        """Set the playhead position in seconds."""
        if self._playhead:
            x = TRACK_HEADER_WIDTH + seconds * self.pixels_per_second
            self._playhead.set_position(x)
    
    def get_playhead_time(self) -> float:
        """Get the current playhead time in seconds."""
        if self._playhead:
            x = self._playhead.get_x_position()
            return max(0, (x - TRACK_HEADER_WIDTH) / self.pixels_per_second)
        return 0.0
    
    def zoom_in(self) -> None:
        """Increase zoom level."""
        self.pixels_per_second = min(200, self.pixels_per_second * 1.25)
        self.refresh_timeline()
    
    def zoom_out(self) -> None:
        """Decrease zoom level."""
        self.pixels_per_second = max(5, self.pixels_per_second / 1.25)
        self.refresh_timeline()
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle scroll wheel for zooming with Ctrl."""
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for playhead positioning."""
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            
            # Check if clicking on ruler area
            if scene_pos.y() < RULER_HEIGHT:
                # Set playhead position
                new_x = max(TRACK_HEADER_WIDTH, scene_pos.x())
                if self._playhead:
                    self._playhead.set_position(new_x)
                    time = (new_x - TRACK_HEADER_WIDTH) / self.pixels_per_second
                    self.time_changed.emit(time)
                event.accept()
                return
        
        super().mousePressEvent(event)


class TimelineWidget(QWidget):
    """
    Main timeline widget combining view with controls.
    
    This is the widget to embed in the main window.
    """
    
    # Forward signals from view
    time_changed = Signal(float)
    clip_selected = Signal(str)
    clip_deleted = Signal(str)
    clip_split_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Timeline view
        self.view = TimelineView()
        layout.addWidget(self.view, stretch=1)
        
        # Controls bar
        controls = QHBoxLayout()
        controls.setContentsMargins(5, 2, 5, 2)
        
        # Zoom controls
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(self.view.zoom_out)
        controls.addWidget(zoom_out_btn)
        
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(5, 200)
        self.zoom_slider.setValue(50)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        controls.addWidget(self.zoom_slider)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(self.view.zoom_in)
        controls.addWidget(zoom_in_btn)
        
        controls.addStretch()
        
        # Time display
        self.time_label = QLabel("00:00:00.000")
        self.time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        controls.addWidget(self.time_label)
        
        controls_widget = QWidget()
        controls_widget.setLayout(controls)
        controls_widget.setFixedHeight(30)
        layout.addWidget(controls_widget)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.view.time_changed.connect(self._on_time_changed)
        self.view.time_changed.connect(self.time_changed)
        self.view.clip_selected.connect(self.clip_selected)
        self.view.clip_deleted.connect(self.clip_deleted)
        self.view.clip_split_requested.connect(self.clip_split_requested)
    
    def _on_time_changed(self, seconds: float) -> None:
        """Update time display."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        self.time_label.setText(f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}")
    
    def _on_zoom_changed(self, value: int) -> None:
        """Handle zoom slider change."""
        self.view.pixels_per_second = float(value)
        self.view.refresh_timeline()
    
    def set_project(self, project: "Project") -> None:
        """Load a project into the timeline."""
        self.view.set_project(project)
    
    def refresh(self) -> None:
        """Refresh the timeline display."""
        self.view.refresh_timeline()
    
    def set_playhead_time(self, seconds: float) -> None:
        """Set the playhead position."""
        self.view.set_playhead_time(seconds)
        self._on_time_changed(seconds)
    
    def get_playhead_time(self) -> float:
        """Get the current playhead time."""
        return self.view.get_playhead_time()
