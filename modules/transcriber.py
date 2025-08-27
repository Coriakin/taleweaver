"""
Transcription module using various ASR approaches for word-level alignment
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

from .utils import format_time, run_command


class Transcriber:
    """Handles audio transcription with word-level timestamps"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.transcriber_type = self._detect_transcriber()
    
    def _detect_transcriber(self) -> str:
        """Detect which transcription backend is available"""
        import shutil
        import os
        
        # Check for parakeet-mlx CLI (preferred for Apple Silicon) - command line tool
        # Check with expanded PATH to include common installation locations
        original_path = os.environ.get('PATH', '')
        expanded_paths = [
            str(Path.home() / ".local" / "bin"),  # pipx default
            "/opt/homebrew/bin",          # Homebrew on Apple Silicon
            "/usr/local/bin",             # Homebrew on Intel
            "~/.local/bin",               # User local installs
        ]
        expanded_path = f"{':'.join(expanded_paths)}:{original_path}"
        os.environ['PATH'] = expanded_path
        
        if shutil.which("parakeet-mlx"):
            self.logger.info("Using parakeet-mlx CLI for transcription (Apple Silicon optimized)")
            os.environ['PATH'] = original_path  # Restore original PATH
            return "parakeet-mlx"
        
        # Restore original PATH
        os.environ['PATH'] = original_path
        
        # Check for parakeet-mlx Python package (if available)
        try:
            import parakeet_mlx
            self.logger.info("Using parakeet-mlx Python package for transcription")
            return "parakeet-mlx-python"
        except ImportError:
            self.logger.debug("parakeet-mlx Python package not found")
        
        # Check for standard parakeet/nemo
        try:
            import nemo.collections.asr as nemo_asr
            self.logger.info("Using NVIDIA NeMo/Parakeet for transcription")
            return "nemo"
        except ImportError:
            self.logger.debug("NVIDIA NeMo not found")
        
        # Check for Whisper with word timestamps (optional fallback)
        try:
            import whisper
            self.logger.info("Using OpenAI Whisper for transcription (fallback)")
            return "whisper"
        except ImportError:
            self.logger.debug("OpenAI Whisper not found")
        
        # Check for wav2vec2 forced alignment
        try:
            import torch
            import torchaudio
            self.logger.info("Using Wav2Vec2 forced alignment (requires known text)")
            return "wav2vec2"
        except ImportError:
            self.logger.debug("PyTorch/TorchAudio not found")
        
        raise ImportError(
            "No supported transcription backend found. Please install one of:\n"
            "- parakeet-mlx (Apple Silicon, recommended): pipx install parakeet-mlx\n"
            "- NVIDIA NeMo: pip install nemo_toolkit[asr]\n"
            "- OpenAI Whisper: pip install openai-whisper\n"
            "- PyTorch Audio: pip install torch torchaudio"
        )
    
    def transcribe_chapters(self, chapters: List[Dict], granularity: str = "word", 
                           force_refresh: bool = False, debug: bool = False) -> Dict[str, Dict]:
        """Transcribe all chapters with word-level timestamps"""
        self.logger.info(f"Transcribing {len(chapters)} chapters with {granularity} granularity")
        
        if debug:
            self.logger.debug(f"Transcription backend: {self.transcriber_type}")
            self.logger.debug(f"Cache directory: {self.cache_dir}")
            self.logger.debug(f"Force refresh: {force_refresh}")
        
        transcriptions = {}
        
        for chapter in chapters:
            chapter_id = str(chapter["id"])
            chapter_path = chapter["path"]
            
            # Check cache
            cache_key = self._get_cache_key(chapter_path, granularity)
            cache_path = self.cache_dir / f"{cache_key}.pkl"
            
            if cache_path.exists() and not force_refresh:
                self.logger.info(f"Loading cached transcription for chapter {chapter['index']}")
                if debug:
                    self.logger.debug(f"Cache file: {cache_path}")
                with open(cache_path, 'rb') as f:
                    transcription_data = pickle.load(f)
                    transcriptions[chapter_id] = transcription_data
                    if debug:
                        segments = len(transcription_data.get('segments', []))
                        self.logger.debug(f"Loaded {segments} segments from cache")
                continue
            
            self.logger.info(f"Transcribing chapter {chapter['index']}: {chapter['title']}")
            
            if debug:
                self.logger.debug(f"Chapter path: {chapter_path}")
                self.logger.debug(f"Chapter duration: {chapter.get('duration', 'unknown')}")
            
            try:
                transcription = self._transcribe_file(chapter_path, granularity)
                transcriptions[chapter_id] = transcription
                
                if debug:
                    segments = len(transcription.get('segments', []))
                    backend = transcription.get('backend', 'unknown')
                    self.logger.debug(f"Transcribed {segments} segments using {backend}")
                
                # Cache the result
                with open(cache_path, 'wb') as f:
                    pickle.dump(transcription, f)
                
                self.logger.info(f"Chapter {chapter['index']} transcribed successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to transcribe chapter {chapter['index']}: {e}")
                if debug:
                    self.logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
                    import traceback
                    self.logger.debug(f"Full traceback: {traceback.format_exc()}")
                # Create a fallback transcription
                fallback_transcription = self._create_fallback_transcription(chapter)
                transcriptions[chapter_id] = fallback_transcription
                if debug:
                    self.logger.debug(f"Created fallback transcription for chapter {chapter['index']}")
        
        return transcriptions
    
    def _transcribe_file(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe a single audio file"""
        if self.transcriber_type == "parakeet-mlx":
            return self._transcribe_with_parakeet_mlx_cli(audio_path, granularity)
        elif self.transcriber_type == "parakeet-mlx-python":
            return self._transcribe_with_parakeet_mlx_python(audio_path, granularity)
        elif self.transcriber_type == "nemo":
            return self._transcribe_with_nemo(audio_path, granularity)
        elif self.transcriber_type == "whisper":
            return self._transcribe_with_whisper(audio_path, granularity)
        elif self.transcriber_type == "wav2vec2":
            return self._transcribe_with_wav2vec2(audio_path, granularity)
        else:
            raise ValueError(f"Unknown transcriber type: {self.transcriber_type}")
    
    def _transcribe_with_parakeet_mlx_cli(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe using parakeet-mlx CLI (Apple Silicon optimized)"""
        import tempfile
        import json
        
        try:
            # Create temporary directory for output
            with tempfile.TemporaryDirectory() as temp_dir:
                # Use parakeet-mlx with JSON output and word highlighting for timestamps
                command = [
                    "parakeet-mlx", 
                    "--output-format", "json",
                    "--highlight-words",  # This should provide word-level timestamps
                    "--output-dir", temp_dir,
                    str(audio_path)
                ]
                
                # Run parakeet-mlx command (PATH should already be set from detection)
                result = run_command(command)
                
                # Find the output JSON file
                import os
                json_files = [f for f in os.listdir(temp_dir) if f.endswith('.json')]
                if not json_files:
                    raise Exception("No JSON output file found from parakeet-mlx")
                
                json_path = os.path.join(temp_dir, json_files[0])
                with open(json_path, 'r') as f:
                    parakeet_output = json.load(f)
                
                # Parse the output and extract segments
                segments = self._parse_parakeet_json_output(parakeet_output, granularity)
                
                return {
                    "text": " ".join([seg["text"] for seg in segments]),
                    "segments": segments,
                    "granularity": granularity,
                    "backend": "parakeet-mlx-cli"
                }
                
        except Exception as e:
            self.logger.error(f"Parakeet-MLX CLI transcription failed: {e}")
            raise
    
    def _transcribe_with_nemo(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe using NVIDIA NeMo/Parakeet"""
        import nemo.collections.asr as nemo_asr
        
        # Load pre-trained model
        asr_model = nemo_asr.models.EncDecRNNTBPEModel.from_pretrained("nvidia/parakeet-rnnt-1.1b")
        
        # Transcribe with timestamps
        transcription = asr_model.transcribe([str(audio_path)], return_hypotheses=True)
        
        # Process the results to extract word-level timestamps
        segments = self._process_nemo_output(transcription[0], granularity)
        
        return {
            "text": " ".join([seg["text"] for seg in segments]),
            "segments": segments,
            "granularity": granularity,
            "backend": "nemo"
        }
    
    def _transcribe_with_whisper(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe using OpenAI Whisper"""
        import whisper
        
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path), word_timestamps=True)
        
        segments = []
        
        if granularity == "word" and "words" in result:
            for word_info in result["words"]:
                segments.append({
                    "text": word_info["word"].strip(),
                    "start": word_info["start"],
                    "end": word_info["end"],
                    "type": "word"
                })
        else:
            # Use sentence-level segments
            for segment in result["segments"]:
                segments.append({
                    "text": segment["text"].strip(),
                    "start": segment["start"],
                    "end": segment["end"],
                    "type": "sentence"
                })
        
        return {
            "text": result["text"],
            "segments": segments,
            "granularity": granularity,
            "backend": "whisper"
        }
    
    def _transcribe_with_wav2vec2(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe using Wav2Vec2 forced alignment (requires known text)"""
        # This would require pre-existing text to align against
        # For now, return a placeholder
        self.logger.warning("Wav2Vec2 forced alignment requires known text - using fallback")
        raise NotImplementedError("Wav2Vec2 alignment requires known text")
    
    def _parse_parakeet_output(self, output: str, granularity: str) -> List[Dict]:
        """Parse parakeet-mlx command output"""
        # This is a placeholder - actual format depends on parakeet-mlx output
        segments = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Expected format: [start_time-end_time] text
            # This is hypothetical - adjust based on actual output format
            try:
                if '[' in line and ']' in line:
                    time_part = line.split(']')[0][1:]  # Remove [
                    text_part = line.split(']')[1].strip()
                    
                    if '-' in time_part:
                        start_str, end_str = time_part.split('-')
                        start_time = float(start_str)
                        end_time = float(end_str)
                        
                        segments.append({
                            "text": text_part,
                            "start": start_time,
                            "end": end_time,
                            "type": granularity
                        })
            except Exception as e:
                self.logger.warning(f"Failed to parse line: {line} - {e}")
                continue
        
        return segments
    
    def _parse_parakeet_json_output(self, parakeet_output: dict, granularity: str) -> List[Dict]:
        """Parse parakeet-mlx JSON output to extract segments with timestamps"""
        segments = []
        
        # Parakeet-MLX format: {"text": "...", "sentences": [...], ...}
        if "sentences" in parakeet_output:
            for sentence_data in parakeet_output["sentences"]:
                sentence_text = sentence_data.get("text", "").strip()
                sentence_start = sentence_data.get("start", 0.0)
                sentence_end = sentence_data.get("end", sentence_start + 1.0)
                
                if granularity == "word" and "tokens" in sentence_data:
                    # Extract word-level tokens
                    current_word = ""
                    word_start = None
                    
                    for token_data in sentence_data["tokens"]:
                        token_text = token_data.get("text", "")
                        token_start = token_data.get("start", 0.0)
                        token_end = token_data.get("end", token_start + 0.1)
                        
                        # Parakeet tokens are sub-word pieces, combine them into words
                        if token_text.startswith(" ") and current_word:
                            # Previous word is complete, add it
                            if current_word.strip():
                                segments.append({
                                    "text": current_word.strip(),
                                    "start": word_start,
                                    "end": token_start,
                                    "type": "word"
                                })
                            # Start new word
                            current_word = token_text
                            word_start = token_start
                        else:
                            # Continue current word
                            if word_start is None:
                                word_start = token_start
                            current_word += token_text
                    
                    # Add the last word
                    if current_word.strip():
                        segments.append({
                            "text": current_word.strip(),
                            "start": word_start,
                            "end": sentence_end,
                            "type": "word"
                        })
                
                elif sentence_text:
                    # Use sentence-level timing
                    segments.append({
                        "text": sentence_text,
                        "start": sentence_start,
                        "end": sentence_end,
                        "type": "sentence"
                    })
        
        elif "text" in parakeet_output:
            # Fallback to full text without detailed timing
            full_text = parakeet_output["text"].strip()
            if full_text:
                segments.append({
                    "text": full_text,
                    "start": 0.0,
                    "end": 1.0,  # Placeholder timing
                    "type": "sentence"
                })
        
        return segments
    
    def _transcribe_with_parakeet_mlx_python(self, audio_path: Path, granularity: str) -> Dict:
        """Transcribe using parakeet-mlx Python package (if available)"""
        # This would be implemented if a Python package becomes available
        raise NotImplementedError("Parakeet-MLX Python package integration not yet implemented")
    
    def _process_nemo_output(self, hypothesis, granularity: str) -> List[Dict]:
        """Process NeMo transcription output"""
        segments = []
        
        # Extract word-level information from NeMo hypothesis
        # This depends on the specific model output format
        if hasattr(hypothesis, 'words') and granularity == "word":
            for word in hypothesis.words:
                segments.append({
                    "text": word.word,
                    "start": word.start_time,
                    "end": word.end_time,
                    "type": "word"
                })
        else:
            # Fallback to sentence level
            text = hypothesis.text
            segments.append({
                "text": text,
                "start": 0.0,
                "end": 0.0,  # Would need to be calculated
                "type": "sentence"
            })
        
        return segments
    
    def _create_fallback_transcription(self, chapter: Dict) -> Dict:
        """Create a fallback transcription when ASR fails"""
        self.logger.warning(f"Creating fallback transcription for chapter {chapter['index']}")
        
        # Create a simple transcription with chapter title
        segments = [{
            "text": chapter["title"],
            "start": 0.0,
            "end": chapter["duration"],
            "type": "sentence"
        }]
        
        return {
            "text": chapter["title"],
            "segments": segments,
            "granularity": "sentence",
            "backend": "fallback"
        }
    
    def _get_cache_key(self, audio_path: Path, granularity: str) -> str:
        """Generate cache key for transcription"""
        content = f"{audio_path.name}_{audio_path.stat().st_mtime}_{granularity}"
        return hashlib.md5(content.encode()).hexdigest()