"""
Project I/O Module

Handles serialization and deserialization of Manual Editor projects.
Projects are saved as JSON files with a .lcproj extension.
"""

import json
import os
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from manual_editor.models.project import Project

# Project file version for migration support
PROJECT_VERSION = "1.0.0"


def save_project(project: "Project", file_path: str) -> bool:
    """
    Saves a project to a JSON file.
    
    Args:
        project: The Project object to save
        file_path: Destination file path (.lcproj)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        data = {
            "version": PROJECT_VERSION,
            "saved_at": datetime.now().isoformat(),
            "project": project.to_dict()
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"Failed to save project: {e}")
        return False


def load_project(file_path: str) -> "Project":
    """
    Loads a project from a JSON file.
    
    Args:
        file_path: Path to the .lcproj file
        
    Returns:
        Project object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    # Import here to avoid circular imports
    from manual_editor.models.project import Project
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Project file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid project file format: {e}")
    
    # Version check for future migrations
    version = data.get("version", "0.0.0")
    if version != PROJECT_VERSION:
        # Future: Add migration logic here
        pass
    
    project_data = data.get("project")
    if not project_data:
        raise ValueError("Project data not found in file")
    
    return Project.from_dict(project_data)


def get_recent_projects(max_count: int = 10) -> list:
    """
    Returns a list of recently opened projects.
    
    Args:
        max_count: Maximum number of recent projects to return
        
    Returns:
        List of (file_path, project_name, last_modified) tuples
    """
    # This would typically read from a config file
    # For now, return empty list
    return []


def export_srt(subtitles: list, output_path: str) -> bool:
    """
    Exports subtitles to SRT format.
    
    Args:
        subtitles: List of Subtitle objects
        output_path: Destination .srt file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, start=1):
                # SRT format:
                # 1
                # 00:00:01,000 --> 00:00:04,000
                # Subtitle text
                
                start = _seconds_to_srt_time(sub.start_time)
                end = _seconds_to_srt_time(sub.start_time + sub.duration)
                
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{sub.text}\n")
                f.write("\n")
        
        return True
        
    except Exception as e:
        print(f"Failed to export SRT: {e}")
        return False


def _seconds_to_srt_time(seconds: float) -> str:
    """
    Converts seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
