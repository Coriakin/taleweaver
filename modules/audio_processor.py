"""
Audio processing module for extracting audiobook chapters
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .utils import run_command, sanitize_filename, format_time


class AudioProcessor:
    """Handles audiobook chapter extraction and metadata processing"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def get_metadata(self, audiobook_path: Path) -> Dict:
        """Extract metadata from audiobook file"""
        self.logger.info(f"Extracting metadata from {audiobook_path}")
        
        command = [
            "ffprobe", 
            "-v", "quiet",
            "-print_format", "json",
            "-show_format", 
            "-show_chapters",
            str(audiobook_path)
        ]
        
        result = run_command(command)
        metadata = json.loads(result.stdout)
        
        # Extract basic metadata
        format_info = metadata.get("format", {})
        tags = format_info.get("tags", {})
        
        return {
            "title": tags.get("title", tags.get("album", "Unknown Title")),
            "author": tags.get("artist", "Unknown Author"),
            "duration": float(format_info.get("duration", 0)),
            "chapters": metadata.get("chapters", []),
            "raw_metadata": metadata
        }
    
    def extract_chapters(self, audiobook_path: Path, force_refresh: bool = False, max_chapters: Optional[int] = None) -> List[Dict]:
        """Extract chapters as individual MP3 files"""
        self.logger.info(f"Extracting chapters from {audiobook_path}")
        
        # Get metadata and chapters
        metadata = self.get_metadata(audiobook_path)
        chapters = metadata["chapters"]
        
        if not chapters:
            self.logger.error("No chapters found in audiobook")
            return []
        
        # Limit chapters if specified
        if max_chapters is not None:
            chapters = chapters[:max_chapters]
            self.logger.info(f"Limited to first {max_chapters} chapters")
        
        extracted_chapters = []
        
        for i, chapter in enumerate(chapters):
            chapter_id = chapter["id"]
            start_time = float(chapter["start_time"])
            end_time = float(chapter["end_time"])
            duration = end_time - start_time
            
            # Get chapter title
            chapter_tags = chapter.get("tags", {})
            chapter_title = chapter_tags.get("title", f"Chapter {i+1}")
            
            # Create safe filename
            safe_title = sanitize_filename(chapter_title)
            chapter_filename = f"{i+1:03d}_{safe_title}.mp3"
            chapter_path = self.cache_dir / chapter_filename
            
            # Check if chapter already exists and skip if not forcing refresh
            if chapter_path.exists() and not force_refresh:
                self.logger.info(f"Chapter {i+1} already exists: {chapter_path}")
            else:
                self.logger.info(f"Extracting chapter {i+1}: {chapter_title}")
                self._extract_chapter(audiobook_path, chapter_path, start_time, end_time)
            
            chapter_info = {
                "id": chapter_id,
                "index": i + 1,
                "title": chapter_title,
                "filename": chapter_filename,
                "path": chapter_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "formatted_duration": format_time(duration)
            }
            
            extracted_chapters.append(chapter_info)
        
        self.logger.info(f"Successfully processed {len(extracted_chapters)} chapters")
        return extracted_chapters
    
    def _extract_chapter(self, input_path: Path, output_path: Path, start_time: float, end_time: float):
        """Extract a single chapter using ffmpeg"""
        command = [
            "ffmpeg",
            "-i", str(input_path),
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c:a", "mp3",
            "-b:a", "128k",
            "-y",  # Overwrite output files
            str(output_path)
        ]
        
        try:
            run_command(command)
            self.logger.debug(f"Chapter extracted: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to extract chapter: {e}")
            raise
    
    def get_chapter_info(self, chapter_path: Path) -> Dict:
        """Get information about an extracted chapter"""
        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(chapter_path)
        ]
        
        result = run_command(command)
        info = json.loads(result.stdout)
        
        format_info = info.get("format", {})
        return {
            "duration": float(format_info.get("duration", 0)),
            "size": int(format_info.get("size", 0)),
            "bitrate": int(format_info.get("bit_rate", 0))
        }