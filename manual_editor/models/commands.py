"""
Command Pattern Implementation for Undo/Redo

This module implements the Command pattern to enable full undo/redo
functionality in the Manual Video Editor. Each modification to the
project is encapsulated as a Command object that can be executed,
undone, and re-executed.

Usage:
    history = CommandHistory()
    
    # Execute a command
    cmd = MoveClipCommand(project, clip_id, new_position)
    history.execute(cmd)
    
    # Undo
    history.undo()
    
    # Redo
    history.redo()
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any, TYPE_CHECKING
from dataclasses import dataclass
import copy

if TYPE_CHECKING:
    from manual_editor.models.project import Project, Clip, AudioClip, Subtitle


class Command(ABC):
    """
    Abstract base class for all commands.
    
    Each command must implement execute() and undo() methods.
    Commands should be completely self-contained and store all
    information needed to reverse their effects.
    """
    
    @abstractmethod
    def execute(self) -> bool:
        """
        Execute the command.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        """
        Reverse the effects of the command.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this command."""
        pass


class CommandHistory:
    """
    Manages the command history for undo/redo operations.
    
    Maintains two stacks:
    - undo_stack: Commands that have been executed
    - redo_stack: Commands that have been undone
    
    When a new command is executed, the redo stack is cleared.
    """
    
    def __init__(self, max_history: int = 100):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_history = max_history
    
    def execute(self, command: Command) -> bool:
        """
        Execute a command and add it to the history.
        
        Args:
            command: The command to execute
            
        Returns:
            True if command executed successfully
        """
        if command.execute():
            self._undo_stack.append(command)
            self._redo_stack.clear()  # Clear redo stack on new action
            
            # Limit history size
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
            
            return True
        return False
    
    def undo(self) -> Optional[Command]:
        """
        Undo the last command.
        
        Returns:
            The undone command, or None if nothing to undo
        """
        if not self._undo_stack:
            return None
        
        command = self._undo_stack.pop()
        if command.undo():
            self._redo_stack.append(command)
            return command
        else:
            # Undo failed, put command back
            self._undo_stack.append(command)
            return None
    
    def redo(self) -> Optional[Command]:
        """
        Redo the last undone command.
        
        Returns:
            The redone command, or None if nothing to redo
        """
        if not self._redo_stack:
            return None
        
        command = self._redo_stack.pop()
        if command.execute():
            self._undo_stack.append(command)
            return command
        else:
            # Redo failed, put command back
            self._redo_stack.append(command)
            return None
    
    def can_undo(self) -> bool:
        """Check if there are commands to undo."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if there are commands to redo."""
        return len(self._redo_stack) > 0
    
    def get_undo_description(self) -> Optional[str]:
        """Get the description of the next command to undo."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get the description of the next command to redo."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return None
    
    def clear(self) -> None:
        """Clear all history."""
        self._undo_stack.clear()
        self._redo_stack.clear()


# ============================================================================
# Clip Commands
# ============================================================================

class AddClipCommand(Command):
    """Command to add a new clip to the project."""
    
    def __init__(self, project: "Project", clip: "Clip"):
        self._project = project
        self._clip = clip
    
    def execute(self) -> bool:
        self._project.add_clip(self._clip)
        return True
    
    def undo(self) -> bool:
        return self._project.remove_clip(self._clip.id)
    
    @property
    def description(self) -> str:
        return f"Add clip: {self._clip.name}"


class DeleteClipCommand(Command):
    """Command to delete a clip from the project."""
    
    def __init__(self, project: "Project", clip_id: str):
        self._project = project
        self._clip_id = clip_id
        self._clip: Optional["Clip"] = None  # Stored for undo
    
    def execute(self) -> bool:
        self._clip = self._project.get_clip_by_id(self._clip_id)
        if self._clip:
            return self._project.remove_clip(self._clip_id)
        return False
    
    def undo(self) -> bool:
        if self._clip:
            self._project.add_clip(self._clip)
            return True
        return False
    
    @property
    def description(self) -> str:
        name = self._clip.name if self._clip else "clip"
        return f"Delete clip: {name}"


class MoveClipCommand(Command):
    """Command to move a clip to a new timeline position."""
    
    def __init__(self, project: "Project", clip_id: str, new_start: float):
        self._project = project
        self._clip_id = clip_id
        self._new_start = new_start
        self._old_start: Optional[float] = None
    
    def execute(self) -> bool:
        clip = self._project.get_clip_by_id(self._clip_id)
        if clip:
            self._old_start = clip.timeline_start
            clip.timeline_start = self._new_start
            return True
        return False
    
    def undo(self) -> bool:
        if self._old_start is not None:
            clip = self._project.get_clip_by_id(self._clip_id)
            if clip:
                clip.timeline_start = self._old_start
                return True
        return False
    
    @property
    def description(self) -> str:
        return "Move clip"


class TrimClipCommand(Command):
    """Command to trim a clip's in/out points."""
    
    def __init__(
        self,
        project: "Project",
        clip_id: str,
        new_in_time: Optional[float] = None,
        new_out_time: Optional[float] = None,
        new_timeline_start: Optional[float] = None
    ):
        self._project = project
        self._clip_id = clip_id
        self._new_in_time = new_in_time
        self._new_out_time = new_out_time
        self._new_timeline_start = new_timeline_start
        
        # Store original values for undo
        self._old_in_time: Optional[float] = None
        self._old_out_time: Optional[float] = None
        self._old_timeline_start: Optional[float] = None
    
    def execute(self) -> bool:
        clip = self._project.get_clip_by_id(self._clip_id)
        if not clip:
            return False
        
        # Store old values
        self._old_in_time = clip.in_time
        self._old_out_time = clip.out_time
        self._old_timeline_start = clip.timeline_start
        
        # Apply new values
        if self._new_in_time is not None:
            clip.in_time = self._new_in_time
        if self._new_out_time is not None:
            clip.out_time = self._new_out_time
        if self._new_timeline_start is not None:
            clip.timeline_start = self._new_timeline_start
        
        return True
    
    def undo(self) -> bool:
        clip = self._project.get_clip_by_id(self._clip_id)
        if not clip:
            return False
        
        if self._old_in_time is not None:
            clip.in_time = self._old_in_time
        if self._old_out_time is not None:
            clip.out_time = self._old_out_time
        if self._old_timeline_start is not None:
            clip.timeline_start = self._old_timeline_start
        
        return True
    
    @property
    def description(self) -> str:
        return "Trim clip"


class SplitClipCommand(Command):
    """
    Command to split a clip at a specific time.
    
    This creates a new clip from the second half and modifies
    the original clip to end at the split point.
    """
    
    def __init__(self, project: "Project", clip_id: str, split_time: float):
        self._project = project
        self._clip_id = clip_id
        self._split_time = split_time
        
        self._new_clip: Optional["Clip"] = None
        self._old_out_time: Optional[float] = None
    
    def execute(self) -> bool:
        from manual_editor.models.project import Clip
        
        clip = self._project.get_clip_by_id(self._clip_id)
        if not clip:
            return False
        
        # Validate split time is within clip
        if not clip.contains_time(self._split_time):
            return False
        
        # Calculate the source time for the split
        time_into_clip = self._split_time - clip.timeline_start
        split_source_time = clip.in_time + time_into_clip
        
        # Store original out time
        self._old_out_time = clip.out_time
        
        # Create new clip for second half
        self._new_clip = Clip.create_new(
            source_file=clip.source_file,
            in_time=split_source_time,
            out_time=clip.out_time,
            timeline_start=self._split_time,
            track_index=clip.track_index
        )
        self._new_clip.name = f"{clip.name} (2)"
        
        # Modify original clip to end at split
        clip.out_time = split_source_time
        
        # Add new clip to project
        self._project.add_clip(self._new_clip)
        
        return True
    
    def undo(self) -> bool:
        if not self._new_clip or self._old_out_time is None:
            return False
        
        # Remove the new clip
        self._project.remove_clip(self._new_clip.id)
        
        # Restore original clip's out time
        clip = self._project.get_clip_by_id(self._clip_id)
        if clip:
            clip.out_time = self._old_out_time
            return True
        
        return False
    
    @property
    def description(self) -> str:
        return "Split clip"


# ============================================================================
# Audio Clip Commands
# ============================================================================

class AddAudioClipCommand(Command):
    """Command to add an audio clip."""
    
    def __init__(self, project: "Project", clip: "AudioClip"):
        self._project = project
        self._clip = clip
    
    def execute(self) -> bool:
        self._project.add_audio_clip(self._clip)
        return True
    
    def undo(self) -> bool:
        return self._project.remove_audio_clip(self._clip.id)
    
    @property
    def description(self) -> str:
        return f"Add audio: {self._clip.name}"


class DeleteAudioClipCommand(Command):
    """Command to delete an audio clip."""
    
    def __init__(self, project: "Project", clip_id: str):
        self._project = project
        self._clip_id = clip_id
        self._clip: Optional["AudioClip"] = None
    
    def execute(self) -> bool:
        self._clip = self._project.get_audio_clip_by_id(self._clip_id)
        if self._clip:
            return self._project.remove_audio_clip(self._clip_id)
        return False
    
    def undo(self) -> bool:
        if self._clip:
            self._project.add_audio_clip(self._clip)
            return True
        return False
    
    @property
    def description(self) -> str:
        name = self._clip.name if self._clip else "audio"
        return f"Delete audio: {name}"


class MoveAudioClipCommand(Command):
    """Command to move an audio clip."""
    
    def __init__(self, project: "Project", clip_id: str, new_start: float):
        self._project = project
        self._clip_id = clip_id
        self._new_start = new_start
        self._old_start: Optional[float] = None
    
    def execute(self) -> bool:
        clip = self._project.get_audio_clip_by_id(self._clip_id)
        if clip:
            self._old_start = clip.timeline_start
            clip.timeline_start = self._new_start
            return True
        return False
    
    def undo(self) -> bool:
        if self._old_start is not None:
            clip = self._project.get_audio_clip_by_id(self._clip_id)
            if clip:
                clip.timeline_start = self._old_start
                return True
        return False
    
    @property
    def description(self) -> str:
        return "Move audio"


class ChangeAudioVolumeCommand(Command):
    """Command to change audio clip volume."""
    
    def __init__(self, project: "Project", clip_id: str, new_volume: float):
        self._project = project
        self._clip_id = clip_id
        self._new_volume = new_volume
        self._old_volume: Optional[float] = None
    
    def execute(self) -> bool:
        clip = self._project.get_audio_clip_by_id(self._clip_id)
        if clip:
            self._old_volume = clip.volume
            clip.volume = self._new_volume
            return True
        return False
    
    def undo(self) -> bool:
        if self._old_volume is not None:
            clip = self._project.get_audio_clip_by_id(self._clip_id)
            if clip:
                clip.volume = self._old_volume
                return True
        return False
    
    @property
    def description(self) -> str:
        return "Change volume"


# ============================================================================
# Subtitle Commands
# ============================================================================

class AddSubtitleCommand(Command):
    """Command to add a subtitle."""
    
    def __init__(self, project: "Project", subtitle: "Subtitle"):
        self._project = project
        self._subtitle = subtitle
    
    def execute(self) -> bool:
        self._project.add_subtitle(self._subtitle)
        return True
    
    def undo(self) -> bool:
        return self._project.remove_subtitle(self._subtitle.id)
    
    @property
    def description(self) -> str:
        text = self._subtitle.text[:20] + "..." if len(self._subtitle.text) > 20 else self._subtitle.text
        return f"Add subtitle: {text}"


class DeleteSubtitleCommand(Command):
    """Command to delete a subtitle."""
    
    def __init__(self, project: "Project", subtitle_id: str):
        self._project = project
        self._subtitle_id = subtitle_id
        self._subtitle: Optional["Subtitle"] = None
    
    def execute(self) -> bool:
        self._subtitle = self._project.get_subtitle_by_id(self._subtitle_id)
        if self._subtitle:
            return self._project.remove_subtitle(self._subtitle_id)
        return False
    
    def undo(self) -> bool:
        if self._subtitle:
            self._project.add_subtitle(self._subtitle)
            return True
        return False
    
    @property
    def description(self) -> str:
        return "Delete subtitle"


class EditSubtitleCommand(Command):
    """Command to edit subtitle properties."""
    
    def __init__(
        self,
        project: "Project",
        subtitle_id: str,
        new_text: Optional[str] = None,
        new_start_time: Optional[float] = None,
        new_duration: Optional[float] = None
    ):
        self._project = project
        self._subtitle_id = subtitle_id
        self._new_text = new_text
        self._new_start_time = new_start_time
        self._new_duration = new_duration
        
        self._old_text: Optional[str] = None
        self._old_start_time: Optional[float] = None
        self._old_duration: Optional[float] = None
    
    def execute(self) -> bool:
        subtitle = self._project.get_subtitle_by_id(self._subtitle_id)
        if not subtitle:
            return False
        
        self._old_text = subtitle.text
        self._old_start_time = subtitle.start_time
        self._old_duration = subtitle.duration
        
        if self._new_text is not None:
            subtitle.text = self._new_text
        if self._new_start_time is not None:
            subtitle.start_time = self._new_start_time
        if self._new_duration is not None:
            subtitle.duration = self._new_duration
        
        return True
    
    def undo(self) -> bool:
        subtitle = self._project.get_subtitle_by_id(self._subtitle_id)
        if not subtitle:
            return False
        
        if self._old_text is not None:
            subtitle.text = self._old_text
        if self._old_start_time is not None:
            subtitle.start_time = self._old_start_time
        if self._old_duration is not None:
            subtitle.duration = self._old_duration
        
        return True
    
    @property
    def description(self) -> str:
        return "Edit subtitle"
