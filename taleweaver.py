#!/usr/bin/env python3
"""
TaleWeaver - EPUB 3 Media Overlay Generator

Generates EPUB 3 files with media overlay support from audiobooks.
Extracts chapters as individual MP3 files and uses advanced speech recognition
for word-level synchronization between text and audio.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from modules.audio_processor import AudioProcessor
from modules.transcriber import Transcriber
from modules.epub_builder import EPUBBuilder
from modules.utils import setup_logging, validate_requirements


def main():
    parser = argparse.ArgumentParser(description="TaleWeaver - Generate EPUB 3 with media overlay from audiobook")
    parser.add_argument("audiobook", help="Path to audiobook file")
    parser.add_argument("-o", "--output", help="Output EPUB filename", default="output.epub")
    parser.add_argument("--original-epub", help="Path to original EPUB file for styling and assets")
    parser.add_argument("--epubcheck-jar", help="Path to epubcheck.jar for EPUB validation (optional)")
    parser.add_argument("--cache-dir", help="Cache directory", default="cache")
    parser.add_argument("--granularity", choices=["word", "sentence"], default="word", 
                       help="Synchronization granularity")
    parser.add_argument("--force-refresh", action="store_true", 
                       help="Force refresh of cached data")
    parser.add_argument("--max-chapters", type=int, help="Maximum number of chapters to process")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Maximum debug output with detailed chapter tracking")
    
    args = parser.parse_args()
    
    # Setup logging
    debug_mode = args.debug or args.verbose
    setup_logging(verbose=debug_mode, debug=args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Validate requirements
        validate_requirements()
        
        # Initialize paths
        audiobook_path = Path(args.audiobook)
        if not audiobook_path.exists():
            logger.error(f"Audiobook file not found: {audiobook_path}")
            sys.exit(1)
            
        cache_dir = Path(args.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = Path(args.output)
        
        logger.info(f"Processing audiobook: {audiobook_path}")
        logger.info(f"Output EPUB: {output_path}")
        logger.info(f"Cache directory: {cache_dir}")
        logger.info(f"Granularity: {args.granularity}")
        
        # Step 1: Process audio and extract chapters
        logger.info("Step 1: Processing audio and extracting chapters...")
        audio_processor = AudioProcessor(cache_dir / "audio")
        chapters = audio_processor.extract_chapters(audiobook_path, force_refresh=args.force_refresh, max_chapters=args.max_chapters)
        
        if not chapters:
            logger.error("No chapters found in audiobook metadata")
            sys.exit(1)
            
        logger.info(f"Found {len(chapters)} chapters")
        
        # Debug: Log all detected chapters
        if args.debug:
            logger.debug("=== DETECTED CHAPTERS ===")
            for i, chapter in enumerate(chapters):
                logger.debug(f"Chapter {i+1}: {chapter['title']} ({chapter['formatted_duration']})")
            logger.debug("=" * 30)
        
        # Step 2: Transcribe chapters
        logger.info("Step 2: Transcribing chapters...")
        transcriber = Transcriber(cache_dir / "transcriptions")
        transcriptions = transcriber.transcribe_chapters(
            chapters, granularity=args.granularity, force_refresh=args.force_refresh, debug=args.debug
        )
        
        # Debug: Log transcription results
        if args.debug:
            logger.debug("=== TRANSCRIPTION RESULTS ===")
            for chapter_id, transcription in transcriptions.items():
                chapter_title = next(c['title'] for c in chapters if str(c['id']) == chapter_id)
                segments_count = len(transcription.get('segments', []))
                backend = transcription.get('backend', 'unknown')
                logger.debug(f"Chapter {chapter_id} ({chapter_title}): {segments_count} segments, backend: {backend}")
            logger.debug("=" * 35)
        
        # Step 3: Build EPUB
        logger.info("Step 3: Building EPUB...")
        epub_builder = EPUBBuilder()
        
        # Get audiobook metadata
        metadata = audio_processor.get_metadata(audiobook_path)
        
        # Check for original EPUB
        original_epub_path = None
        if args.original_epub:
            original_epub_path = Path(args.original_epub)
            if not original_epub_path.exists():
                logger.warning(f"Original EPUB file not found: {original_epub_path}")
                original_epub_path = None
            else:
                logger.info(f"Using original EPUB for enhanced styling: {original_epub_path}")
        
        # Generate EPUB
        epub_path = epub_builder.create_epub(
            chapters=chapters,
            transcriptions=transcriptions,
            metadata=metadata,
            output_path=output_path,
            original_epub_path=original_epub_path
        )
        
        logger.info(f"EPUB created successfully: {epub_path}")
        
        # Step 4: Validate EPUB (only if explicitly requested)
        if args.epubcheck_jar:
            logger.info("Step 4: Validating EPUB...")
            epubcheck_jar_path = Path(args.epubcheck_jar)
            if not epubcheck_jar_path.exists():
                logger.warning(f"Specified epubcheck jar not found: {epubcheck_jar_path}")
            else:
                epub_builder.validate_epub(epub_path, epubcheck_jar_path)
        else:
            logger.info("Skipping EPUB validation (use --epubcheck-jar to enable)")
        
        logger.info("Process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()