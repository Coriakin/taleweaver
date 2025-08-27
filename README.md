# TaleWeaver - An EPUB 3 Media Overlay Generator

_Note: This project is new and I have not battle tested it with many books apart from a few I am reading. I am also doing this on my very limited spare time so bear with me._

# Why and what

__TLDR:__ _Make audiobook into "immersive" experience._

I am sure I have some kind of condition, and that condition is that unless a book is REALLY good from the get go, I may have trouble being consistent with my reading habit even when I think it may be a good read.

What took my reading to a new level was when Amazon introduced the immersive reading where I could buy a book + audiobook combo and then have the Kindle app highlight the words for me as the audiobook was playing. Meaning that I get the best of both worlds and make it easier for me to stay on track when my mind starts drifting.

I have spent __a lot__ of money on kindle books at this stage, but I do buy books from other sources too and missed the flexibility to have this immersive reading experience if I bought anything outside the Amazon eco system.

So, I thought, I do have some coding experience and in this day and age I can always "vibe code" when I get tired.

The result is this standalone Python application that generates EPUB 3 files with so called "media overlay" support from audiobooks you have. It extracts chapters, transcribes audio with word-level timing, and creates this type of immersive synchronized text-audio experiences one would normally only get within the Amazon ecosystem nowadays.


## ✨ Features

- **📚 Chapter Extraction**: Automatically extracts chapters from audiobook metadata
- **🗣️ Speech Recognition**: Multiple transcription backends (Parakeet-MLX, Whisper, NeMo)
- **🎯 Word-Level Sync**: Creates precise text-to-audio synchronization
- **🎨 Enhanced Styling**: Uses original EPUB formatting and artwork when available
- **⚡ Caching**: Smart caching for faster re-runs
- **📱 EPUB 3 Compliance**: Generates valid EPUB 3 files with media overlay support
- **🔍 Validation**: Optional EPUB validation using epubcheck

## 🚀 Quick Start

### Automated Setup (Recommended)

1. **Run the setup script:**
   ```bash
   python setup.py
   ```
   This will guide you through installing all dependencies.

### Manual Installation

1. **Install system dependencies:**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # Optional: Java for EPUB validation
   brew install openjdk  # macOS
   ```

2. **Install Python dependencies:**
   ```bash
   pip install beautifulsoup4 lxml
   ```

3. **Install transcription backend (choose one):**
   
   **🍎 Apple Silicon (recommended):**
   ```bash
   pipx install parakeet-mlx
   ```
   
   **🌐 Universal (fallback):**
   ```bash
   pip install openai-whisper
   ```
   
   **🚀 NVIDIA GPU:**
   ```bash
   pip install nemo_toolkit[asr]
   ```

## 📖 Usage

### Basic Usage

```bash
# Generate EPUB from audiobook
python taleweaver.py audiobook.m4a -o output.epub

# Use original EPUB for enhanced styling
python taleweaver.py audiobook.m4a \
  --original-epub original.epub \
  -o enhanced_output.epub

# With custom epubcheck location
python taleweaver.py audiobook.m4a \
  --epubcheck-jar /path/to/epubcheck.jar \
  -o validated_output.epub
```

### Advanced Options

```bash
python taleweaver.py audiobook.m4a \
  --original-epub original.epub \        # Use original EPUB styling
  --epubcheck-jar epubcheck.jar \        # Custom epubcheck location
  --granularity word \                   # word|sentence level sync
  --cache-dir ./cache \                  # Custom cache directory
  --max-chapters 5 \                     # Limit chapters (testing)
  --force-refresh \                      # Ignore cache
  --verbose                              # Detailed output
```

### Arguments

- `audiobook`: Path to audiobook file (M4A, MP3, etc.)
- `-o, --output`: Output EPUB filename (default: output.epub)
- `--original-epub`: Path to original EPUB for styling and assets
- `--epubcheck-jar`: Path to epubcheck.jar for validation (optional)
- `--cache-dir`: Cache directory for transcriptions and audio (default: cache)
- `--granularity`: Synchronization level - `word` or `sentence` (default: word)
- `--max-chapters`: Maximum number of chapters to process (for testing)
- `--force-refresh`: Force refresh of cached data
- `-v, --verbose`: Verbose output

## 🎯 Standalone Features

- **Minimal Dependencies**: Only requires ffmpeg (widely available)
- **Optional Validation**: epubcheck is optional, not required
- **Auto-Detection**: Automatically detects available transcription engines
- **Portable**: Self-contained with minimal external dependencies
- **Flexible Backends**: Choose the transcription engine that works best for your system

## 🔧 Dependencies

### System Requirements
- **Python 3.8+**
- **ffmpeg** - Audio processing (system package)

### Python Dependencies
- **beautifulsoup4** - HTML/XML parsing  
- **lxml** - XML processing

### Transcription Backend (Choose One)
- **parakeet-mlx** - Apple Silicon transcription (recommended for M1/M2 Macs)
- **openai-whisper** - Universal transcription (works everywhere)
- **nemo_toolkit[asr]** - NVIDIA GPU transcription (for CUDA systems)
- **torch + torchaudio** - PyTorch-based transcription (experimental)

### Optional (Validation)
- **Java** + **epubcheck.jar** - EPUB validation (enhances output quality)

## 🔧 Configuration

### EPUB Validation (Optional)

- Download from: https://github.com/w3c/epubcheck/releases
- Place `epubcheck.jar` in current directory, or
- Use `--epubcheck-jar /path/to/epubcheck.jar`

## Output

The script generates:

1. **EPUB file** with media overlay support
2. **Cached audio files** (individual chapter MP3s)
3. **Cached transcriptions** (for faster re-runs)
4. **Validation report** using epubcheck

## File Structure

```
taleweaver/
├── taleweaver.py              # Main script
├── modules/
│   ├── audio_processor.py     # Chapter extraction to MP3
│   ├── transcriber.py         # Speech recognition integration  
│   ├── epub_builder.py        # EPUB structure generation
│   └── utils.py               # Utility functions
├── cache/
│   ├── audio/                 # Extracted chapter MP3 files
│   └── transcriptions/        # Cached transcription data
├── output/                    # Generated EPUB files
├── test-resources/            # Test audiobook and epubcheck tool
├── venv/                      # Python virtual environment
└── README.md                  # This documentation
```

## EPUB Structure Generated

The generated EPUB includes:

- **META-INF/container.xml**: Container declaration
- **OEBPS/content.opf**: Package document with media overlay metadata
- **OEBPS/toc.ncx**: Navigation for older readers
- **OEBPS/Text/nav.xhtml**: EPUB 3 navigation
- **OEBPS/Text/chapter_XXX.xhtml**: Chapter content with synchronized IDs
- **OEBPS/Text/chapter_XXX.smil**: SMIL files mapping text to audio
- **OEBPS/Audio/XXX_Chapter_Name.mp3**: Individual chapter audio files
- **OEBPS/Styles/style.css**: Basic styling

## Tested Audiobooks

- ✅ M4A with chapter metadata (like iTunes audiobooks)
- ✅ MP3 with chapter metadata  
- ⚠️ Files without chapter metadata will exit with error

## Example Usage Scenarios

- **Personal audiobook collection**: Convert your legally owned audiobooks to enhanced EPUB format
- **Accessibility**: Create synchronized text-audio versions for improved accessibility
- **Educational content**: Transform lecture recordings into interactive study materials
- **Language learning**: Create immersive reading experiences with audio synchronization

## Notes

- First run will be slower due to model downloads and transcription
- Subsequent runs use cached data and are much faster
- Word-level granularity works best with clear speech
- Sentence-level granularity is more reliable for lower quality audio
- Generated EPUBs work with media overlay capable readers like Adobe Digital Editions