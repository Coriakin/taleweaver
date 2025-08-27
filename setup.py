#!/usr/bin/env python3
"""
Setup script for TaleWeaver EPUB Generator
Helps install dependencies and check system requirements
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def check_system_dependencies():
    """Check for required system dependencies"""
    print("Checking system dependencies...")
    
    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg not found")
        print("   Please install ffmpeg:")
        if platform.system() == "Darwin":
            print("   brew install ffmpeg")
        elif platform.system() == "Linux":
            print("   sudo apt-get install ffmpeg  # Ubuntu/Debian")
            print("   sudo yum install ffmpeg      # RHEL/CentOS")
        else:
            print("   Download from: https://ffmpeg.org/download.html")
        return False
    else:
        print("✅ ffmpeg found")
    
    # Check Java (optional)
    if not shutil.which("java"):
        print("⚠️  Java not found (optional for EPUB validation)")
        print("   Install Java 8+ for EPUB validation support")
    else:
        print("✅ Java found")
    
    return True


def install_python_dependencies():
    """Install minimal Python dependencies"""
    print("\nInstalling Python dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "beautifulsoup4>=4.11.0", 
            "lxml>=4.9.0"
        ], check=True)
        print("✅ Core dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install core dependencies")
        return False
    
    return True


def install_transcription_backend():
    """Help user choose and install a transcription backend"""
    print("\nChoosing transcription backend...")
    
    system = platform.system()
    machine = platform.machine()
    
    if system == "Darwin" and machine == "arm64":
        print("🍎 Apple Silicon Mac detected")
        print("Recommended: parakeet-mlx (optimized for Apple Silicon)")
        
        choice = input("Install parakeet-mlx? [Y/n]: ").strip().lower()
        if choice in ['', 'y', 'yes']:
            try:
                # Try pipx first (recommended)
                if shutil.which("pipx"):
                    subprocess.run(["pipx", "install", "parakeet-mlx"], check=True)
                else:
                    print("pipx not found, installing with pip...")
                    subprocess.run([sys.executable, "-m", "pip", "install", "parakeet-mlx"], check=True)
                print("✅ parakeet-mlx installed")
                return True
            except subprocess.CalledProcessError:
                print("❌ Failed to install parakeet-mlx")
    
    print("\nAlternative transcription backends:")
    print("1. OpenAI Whisper (universal, slower)")
    print("2. NVIDIA NeMo (NVIDIA GPUs)")
    print("3. Skip (install manually later)")
    
    choice = input("Choose option [1-3]: ").strip()
    
    if choice == "1":
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "openai-whisper"], check=True)
            print("✅ OpenAI Whisper installed")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install OpenAI Whisper")
    
    elif choice == "2":
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "nemo_toolkit[asr]"], check=True)
            print("✅ NVIDIA NeMo installed")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install NVIDIA NeMo")
    
    else:
        print("⚠️  Skipping transcription backend installation")
        print("   You'll need to install one manually before using TaleWeaver")
    
    return False


def download_epubcheck():
    """Help user download epubcheck for validation"""
    print("\nEPUB validation setup...")
    
    epubcheck_dir = Path("test-resources/epubcheck-5.1.0")
    if epubcheck_dir.exists():
        print("✅ epubcheck already available")
        return True
    
    choice = input("Download epubcheck for EPUB validation? [Y/n]: ").strip().lower()
    if choice in ['', 'y', 'yes']:
        print("Please download epubcheck from:")
        print("https://github.com/w3c/epubcheck/releases/latest")
        print(f"Extract to: {epubcheck_dir}")
        print("Or use --epubcheck-jar /path/to/epubcheck.jar when running TaleWeaver")
    
    return False


def main():
    """Main setup function"""
    print("🔧 TaleWeaver EPUB Generator Setup")
    print("=" * 40)
    
    # Check system dependencies
    if not check_system_dependencies():
        print("\n❌ System dependencies missing. Please install them first.")
        sys.exit(1)
    
    # Install Python dependencies
    if not install_python_dependencies():
        print("\n❌ Failed to install Python dependencies")
        sys.exit(1)
    
    # Install transcription backend
    install_transcription_backend()
    
    # Setup epubcheck
    download_epubcheck()
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Test the installation:")
    print("   python taleweaver.py --help")
    print("2. Generate your first EPUB:")
    print("   python taleweaver.py your_audiobook.m4a -o output.epub")
    
    if Path("test-resources").exists():
        print("3. Try with the sample audiobook:")
        print("   python taleweaver.py test-resources/*.m4a -o sample.epub")


if __name__ == "__main__":
    main()
