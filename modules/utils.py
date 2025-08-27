"""
Utility functions for EPUB generator
"""

import logging
import shutil
import subprocess
import sys
from pathlib import Path


def setup_logging(verbose=False, debug=False):
    """Setup logging configuration"""
    if debug:
        level = logging.DEBUG
        format_str = '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    elif verbose:
        level = logging.DEBUG
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    else:
        level = logging.INFO
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt='%H:%M:%S'
    )


def validate_requirements():
    """Validate that required tools are available"""
    logger = logging.getLogger(__name__)
    
    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found. Please install ffmpeg.")
        sys.exit(1)
    
    # Check ffprobe
    if not shutil.which("ffprobe"):
        logger.error("ffprobe not found. Please install ffmpeg.")
        sys.exit(1)
    
    # Check for transcription backends
    transcription_backends = []
    
    # Check for parakeet-mlx CLI (preferred for Apple Silicon)
    if shutil.which("parakeet-mlx"):
        transcription_backends.append("parakeet-mlx-cli")
        logger.info("Found parakeet-mlx CLI (Apple Silicon optimized)")
    
    # Check for parakeet-mlx Python package
    try:
        import parakeet_mlx
        transcription_backends.append("parakeet-mlx")
        logger.info("Found parakeet-mlx Python package")
    except ImportError:
        pass
    
    # Check for NeMo/Parakeet
    try:
        import nemo.collections.asr
        transcription_backends.append("nemo")
        logger.info("Found NVIDIA NeMo/Parakeet")
    except ImportError:
        pass
        
    # Check for Whisper (optional fallback)
    try:
        import whisper
        transcription_backends.append("whisper")
        logger.info("Found OpenAI Whisper")
    except ImportError:
        logger.debug("OpenAI Whisper not found (optional)")
    
    # Check for PyTorch (for wav2vec2)
    try:
        import torch, torchaudio
        transcription_backends.append("wav2vec2")
        logger.info("Found PyTorch/TorchAudio")
    except ImportError:
        logger.debug("PyTorch not found (optional)")
    
    if not transcription_backends:
        logger.error("No transcription backend found. Please install one of:")
        logger.error("  - parakeet-mlx (Apple Silicon, recommended): pipx install parakeet-mlx")
        logger.error("  - NVIDIA NeMo: pip install nemo_toolkit[asr]")
        logger.error("  - OpenAI Whisper: pip install openai-whisper")
        logger.error("  - PyTorch: pip install torch torchaudio")
        sys.exit(1)
    else:
        logger.info(f"Available transcription backends: {', '.join(transcription_backends)}")


def run_command(command, cwd=None, capture_output=True):
    """Run a shell command and return result"""
    logger = logging.getLogger(__name__)
    
    if isinstance(command, list):
        cmd_str = ' '.join(command)
    else:
        cmd_str = command
        command = command.split()
    
    logger.debug(f"Running command: {cmd_str}")
    
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd_str}")
        logger.error(f"Error: {e.stderr}")
        raise


def sanitize_filename(filename):
    """Sanitize filename for cross-platform compatibility and URL safety"""
    # Remove or replace problematic characters
    forbidden_chars = '<>:"/\\|?* '  # Added space to forbidden chars
    for char in forbidden_chars:
        filename = filename.replace(char, '_')
    
    # Replace multiple underscores with single
    while '__' in filename:
        filename = filename.replace('__', '_')
    
    # Trim underscores and dots
    filename = filename.strip('._')
    
    # Ensure it's not too long
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename


def format_time(seconds):
    """Format seconds as HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def parse_time(time_str):
    """Parse time string HH:MM:SS.mmm to seconds"""
    parts = time_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"Invalid time format: {time_str}")
    
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    
    return hours * 3600 + minutes * 60 + seconds