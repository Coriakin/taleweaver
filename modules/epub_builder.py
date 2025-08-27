"""
EPUB 3 builder with media overlay support
"""

import json
import logging
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup

from .utils import format_time, run_command, sanitize_filename


class EPUBBuilder:
    """Builds EPUB 3 files with media overlay support"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_epub_data = None
    
    def create_epub(self, chapters: List[Dict], transcriptions: Dict[str, Dict], 
                    metadata: Dict, output_path: Path, original_epub_path: Optional[Path] = None) -> Path:
        """Create complete EPUB file"""
        self.logger.info("Building EPUB structure...")
        
        # Extract original EPUB data if provided
        if original_epub_path and original_epub_path.exists():
            self.logger.info(f"Using original EPUB for styling and assets: {original_epub_path}")
            self.original_epub_data = self._extract_original_epub_data(original_epub_path)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_dir = Path(temp_dir) / "epub"
            epub_dir.mkdir()
            
            # Create EPUB directory structure
            meta_inf_dir = epub_dir / "META-INF"
            oebps_dir = epub_dir / "OEBPS"
            audio_dir = oebps_dir / "Audio"
            text_dir = oebps_dir / "Text"
            styles_dir = oebps_dir / "Styles"
            images_dir = oebps_dir / "Images"
            
            for dir_path in [meta_inf_dir, oebps_dir, audio_dir, text_dir, styles_dir, images_dir]:
                dir_path.mkdir(parents=True, exist_ok=True)
            
            # Generate unique ID for this EPUB
            epub_id = str(uuid.uuid4())
            
            # Step 1: Create mimetype file
            self._create_mimetype(epub_dir)
            
            # Step 2: Create META-INF/container.xml
            self._create_container_xml(meta_inf_dir)
            
            
            # Step 3: Copy original EPUB assets if available
            if self.original_epub_data:
                self._copy_original_assets(oebps_dir, styles_dir, images_dir)
            
            # Step 4: Copy audio files
            self._copy_audio_files(chapters, audio_dir)
            
            # Step 5: Create CSS styles (enhanced with original if available)
            self._create_styles(styles_dir)
            
            # Step 6: Create XHTML and SMIL files for each chapter
            chapter_manifests = []
            for chapter in chapters:
                chapter_id = str(chapter["id"])
                transcription = transcriptions.get(chapter_id, {})
                
                xhtml_file, smil_file = self._create_chapter_files(
                    chapter, transcription, text_dir
                )
                
                chapter_manifests.append({
                    "chapter": chapter,
                    "xhtml_file": xhtml_file,
                    "smil_file": smil_file,
                    "transcription": transcription
                })
            
            # Step 7: Create package document (content.opf)
            self._create_package_document(oebps_dir, epub_id, metadata, chapters, chapter_manifests)
            
            # Step 8: Create navigation documents
            self._create_toc_ncx(oebps_dir, epub_id, metadata, chapters)
            self._create_nav_xhtml(text_dir, chapters)
            
            # Step 9: Package into EPUB file
            epub_path = self._package_epub(epub_dir, output_path)
        
        self.logger.info(f"EPUB created: {epub_path}")
        return epub_path

    def _extract_original_epub_data(self, original_epub_path: Path) -> Dict:
        """Extract useful data from original EPUB"""
        self.logger.info("Extracting original EPUB data...")
        
        original_data = {
            'css_files': {},
            'images': {},
            'chapters': {},
            'metadata': {},
            'cover_image': None
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_dir = Path(temp_dir) / "original"
            extract_dir.mkdir()
            
            # Extract original EPUB
            with zipfile.ZipFile(original_epub_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            oebps_dir = extract_dir / "OEBPS"
            if not oebps_dir.exists():
                self.logger.warning("No OEBPS directory found in original EPUB")
                return original_data
            
            # Extract CSS files
            css_dir = oebps_dir / "css"
            if css_dir.exists():
                for css_file in css_dir.glob("*.css"):
                    with open(css_file, 'r', encoding='utf-8') as f:
                        original_data['css_files'][css_file.name] = f.read()
            
            # Extract images and copy them to temp location for later use
            for img_dir_name in ['image', 'images', 'Image', 'Images']:
                img_dir = oebps_dir / img_dir_name
                if img_dir.exists():
                    for img_file in img_dir.glob("*"):
                        if img_file.is_file() and img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.svg']:
                            # Read image data into memory
                            with open(img_file, 'rb') as f:
                                original_data['images'][img_file.name] = f.read()
                            # Check if this might be the cover
                            if 'cover' in img_file.name.lower():
                                original_data['cover_image'] = img_file.name
            
            # Extract chapter content structure
            for xhtml_file in oebps_dir.glob("*.xhtml"):
                if "content" in xhtml_file.name.lower() and xhtml_file.stat().st_size > 1000:  # Skip small files
                    try:
                        with open(xhtml_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            soup = BeautifulSoup(content, 'xml')
                            
                            # Extract chapter structure and styling classes
                            chapter_info = {
                                'title_element': None,
                                'body_classes': [],
                                'paragraph_classes': []
                            }
                            
                            # Find title elements
                            for element in soup.find_all(['h1', 'h2', 'h3', 'p']):
                                if element.get('class'):
                                    classes = element.get('class')
                                    if any(keyword in ' '.join(classes).lower() for keyword in ['chapter', 'title', 'heading']):
                                        chapter_info['title_element'] = {
                                            'tag': element.name,
                                            'classes': classes,
                                            'text': element.get_text().strip()
                                        }
                                        break
                            
                            # Collect common paragraph classes
                            for p in soup.find_all('p'):
                                if p.get('class'):
                                    chapter_info['paragraph_classes'].extend(p.get('class'))
                            
                            # Remove duplicates
                            chapter_info['paragraph_classes'] = list(set(chapter_info['paragraph_classes']))
                            
                            original_data['chapters'][xhtml_file.name] = chapter_info
                    except Exception as e:
                        self.logger.debug(f"Could not parse {xhtml_file.name}: {e}")
        
        self.logger.info(f"Extracted {len(original_data['css_files'])} CSS files and {len(original_data['images'])} images from original EPUB")
        return original_data

    def _copy_original_assets(self, oebps_dir: Path, styles_dir: Path, images_dir: Path):
        """Copy assets from original EPUB"""
        if not self.original_epub_data:
            return
        
        # Copy CSS files
        for css_name, css_content in self.original_epub_data['css_files'].items():
            css_path = styles_dir / css_name
            with open(css_path, 'w', encoding='utf-8') as f:
                f.write(css_content)
            self.logger.debug(f"Copied original CSS: {css_name}")
        
        # Copy images from memory
        for img_name, img_data in self.original_epub_data['images'].items():
            dest_path = images_dir / img_name
            with open(dest_path, 'wb') as f:
                f.write(img_data)
            self.logger.debug(f"Copied original image: {img_name}")

    def _create_mimetype(self, epub_dir: Path):
        """Create mimetype file"""
        mimetype_path = epub_dir / "mimetype"
        with open(mimetype_path, 'w', encoding='utf-8') as f:
            f.write("application/epub+zip")
    
    def _create_container_xml(self, meta_inf_dir: Path):
        """Create META-INF/container.xml"""
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        
        with open(meta_inf_dir / "container.xml", 'w', encoding='utf-8') as f:
            f.write(container_xml)
    
    def _copy_audio_files(self, chapters: List[Dict], audio_dir: Path):
        """Copy chapter audio files to EPUB"""
        for chapter in chapters:
            source_path = chapter["path"]
            dest_path = audio_dir / chapter["filename"]
            
            self.logger.debug(f"Copying audio: {source_path} -> {dest_path}")
            shutil.copy2(source_path, dest_path)
    
    def _create_styles(self, styles_dir: Path):
        """Create CSS stylesheet"""
        css_content = """/* EPUB Media Overlay Styles */

body {
    font-family: serif;
    line-height: 1.5;
    margin: 2em;
}

h1, h2, h3 {
    color: #333;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

.chapter-title {
    font-size: 1.5em;
    font-weight: bold;
    margin-bottom: 1em;
}

.sentence, .word {
    /* Styles for media overlay elements */
}

.playing {
    background-color: yellow;
    /* Highlight currently playing text */
}

.navBar {
    text-align: center;
    margin: 1em 0;
}

.sepBar {
    border: none;
    border-top: 1px solid #ccc;
    margin: 1em 0;
}

.audio-controls {
    text-align: center;
    margin: 2em 0;
}"""
        
        with open(styles_dir / "style.css", 'w', encoding='utf-8') as f:
            f.write(css_content)
    
    def _create_chapter_files(self, chapter: Dict, transcription: Dict, text_dir: Path) -> tuple:
        """Create XHTML and SMIL files for a chapter"""
        chapter_num = chapter["index"]
        safe_title = sanitize_filename(chapter["title"])
        
        xhtml_filename = f"chapter_{chapter_num:03d}.xhtml"
        smil_filename = f"chapter_{chapter_num:03d}.smil"
        
        # Create XHTML file
        xhtml_content = self._generate_xhtml_content(chapter, transcription)
        with open(text_dir / xhtml_filename, 'w', encoding='utf-8') as f:
            f.write(xhtml_content)
        
        # Create SMIL file
        smil_content = self._generate_smil_content(chapter, transcription, xhtml_filename)
        with open(text_dir / smil_filename, 'w', encoding='utf-8') as f:
            f.write(smil_content)
        
        return xhtml_filename, smil_filename
    
    def _generate_xhtml_content(self, chapter: Dict, transcription: Dict) -> str:
        """Generate XHTML content for a chapter with enhanced styling from original EPUB"""
        chapter_num = chapter["index"]
        title = chapter["title"]
        
        # Build CSS links - include original stylesheets if available
        css_links = []
        if self.original_epub_data and self.original_epub_data['css_files']:
            for css_name in self.original_epub_data['css_files'].keys():
                css_links.append(f'    <link rel="stylesheet" href="../Styles/{css_name}" type="text/css"/>')
        css_links.append('    <link rel="stylesheet" href="../Styles/style.css" type="text/css"/>')
        
        # Determine styling classes from original EPUB
        title_class = "chapter-title"
        body_class = "chapter-content"
        paragraph_class = "Body_Text"
        
        if self.original_epub_data and self.original_epub_data['chapters']:
            # Try to find appropriate classes from original chapters
            for chapter_info in self.original_epub_data['chapters'].values():
                if chapter_info.get('title_element'):
                    title_element = chapter_info['title_element']
                    if title_element.get('classes'):
                        title_class = ' '.join(title_element['classes'])
                
                if chapter_info.get('paragraph_classes'):
                    # Use the first body text class we find
                    for cls in chapter_info['paragraph_classes']:
                        if any(keyword in cls.lower() for keyword in ['body', 'text', 'paragraph']):
                            paragraph_class = cls
                            break
        
        # Start building XHTML with enhanced structure
        xhtml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">',
            '<head>',
            f'    <title>{title}</title>',
        ]
        xhtml_lines.extend(css_links)
        xhtml_lines.extend([
            '</head>',
            '<body>',
            f'    <div class="Basic-Text-Frame">',
            f'        <section epub:type="chapter" id="chapter_{chapter_num:03d}">',
        ])
        
        # Add chapter title with original styling
        if "prologue" in title.lower():
            xhtml_lines.append(f'            <p class="Chapter_Book" id="title_{chapter_num:03d}"><a id="_idTextAnchor{chapter_num:03d}"/>{title.upper()}</p>')
        elif any(keyword in title.lower() for keyword in ['part', 'book']):
            xhtml_lines.append(f'            <p class="Part_Title" id="title_{chapter_num:03d}">{title.upper()}</p>')
        else:
            xhtml_lines.append(f'            <h1 class="{title_class}" id="title_{chapter_num:03d}"><span>{title}</span></h1>')
        
        # Add transcription content with enhanced formatting
        segments = transcription.get("segments", [])
        if segments:
            current_paragraph = []
            paragraph_count = 0
            
            for i, segment in enumerate(segments):
                segment_id = f"seg_{chapter_num:03d}_{i:03d}"
                text = segment["text"].strip()
                segment_type = segment.get("type", "sentence")
                
                if text:
                    # Group sentences into paragraphs for better readability
                    current_paragraph.append(f'<span id="{segment_id}" class="{segment_type}">{text}</span>')
                    
                    # Create paragraph breaks at natural points
                    if (len(current_paragraph) >= 3 and 
                        (text.endswith('.') or text.endswith('!') or text.endswith('?')) and
                        i < len(segments) - 1):
                        
                        paragraph_count += 1
                        paragraph_content = ' '.join(current_paragraph)
                        
                        # Use original paragraph class or fallback
                        p_class = paragraph_class if paragraph_count == 1 else paragraph_class
                        xhtml_lines.append(f'            <p class="{p_class}">{paragraph_content}</p>')
                        current_paragraph = []
            
            # Add any remaining content
            if current_paragraph:
                paragraph_content = ' '.join(current_paragraph)
                xhtml_lines.append(f'            <p class="{paragraph_class}">{paragraph_content}</p>')
        else:
            # Fallback content
            xhtml_lines.append(f'            <p class="{paragraph_class}"><span id="fallback_{chapter_num:03d}">Audio content for {title}</span></p>')
        
        xhtml_lines.extend([
            '        </section>',
            '    </div>',
            '</body>',
            '</html>'
        ])
        
        return '\n'.join(xhtml_lines)
    
    def _generate_smil_content(self, chapter: Dict, transcription: Dict, xhtml_filename: str) -> str:
        """Generate SMIL content for a chapter"""
        chapter_num = chapter["index"]
        audio_filename = f"../Audio/{chapter['filename']}"
        
        smil_lines = [
            '<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">',
            '<body>',
            f'    <seq id="seq_{chapter_num:03d}" epub:textref="{xhtml_filename}" epub:type="bodymatter chapter">',
        ]
        
        # Add title mapping
        smil_lines.append(f'        <par id="par_title_{chapter_num:03d}">'),
        smil_lines.append(f'            <text src="{xhtml_filename}#title_{chapter_num:03d}"/>'),
        smil_lines.append(f'            <audio clipBegin="0:00:00.000" clipEnd="0:00:01.000" src="{audio_filename}"/>'),
        smil_lines.append('        </par>')
        
        # Add segment mappings
        segments = transcription.get("segments", [])
        if segments:
            for i, segment in enumerate(segments):
                segment_id = f"seg_{chapter_num:03d}_{i:03d}"
                start_time = format_time(segment.get("start", 0.0))
                end_time = format_time(segment.get("end", segment.get("start", 0.0) + 1.0))
                
                smil_lines.extend([
                    f'        <par id="par_{segment_id}">',
                    f'            <text src="{xhtml_filename}#{segment_id}"/>',
                    f'            <audio clipBegin="{start_time}" clipEnd="{end_time}" src="{audio_filename}"/>',
                    '        </par>'
                ])
        else:
            # Fallback mapping for entire chapter
            duration = format_time(chapter["duration"])
            smil_lines.extend([
                f'        <par id="par_fallback_{chapter_num:03d}">',
                f'            <text src="{xhtml_filename}#fallback_{chapter_num:03d}"/>',
                f'            <audio clipBegin="0:00:00.000" clipEnd="{duration}" src="{audio_filename}"/>',
                '        </par>'
            ])
        
        smil_lines.extend([
            '    </seq>',
            '</body>',
            '</smil>'
        ])
        
        return '\n'.join(smil_lines)
    
    def _create_package_document(self, oebps_dir: Path, epub_id: str, metadata: Dict, 
                                chapters: List[Dict], chapter_manifests: List[Dict]):
        """Create content.opf package document"""
        now = datetime.now().isoformat() + 'Z'
        
        # Create XML structure
        root = ET.Element('package')
        root.set('xmlns', 'http://www.idpf.org/2007/opf')
        root.set('version', '3.0')
        root.set('unique-identifier', 'pubID')
        root.set('xml:lang', 'en')
        root.set('prefix', 'rendition: http://www.idpf.org/vocab/rendition/# media: http://www.idpf.org/vocab/overlays/#')
        
        # Metadata section
        metadata_elem = ET.SubElement(root, 'metadata')
        metadata_elem.set('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        metadata_elem.set('xmlns:opf', 'http://www.idpf.org/2007/opf')
        
        # Basic metadata
        identifier = ET.SubElement(metadata_elem, 'dc:identifier')
        identifier.set('id', 'pubID')
        identifier.text = f'urn:uuid:{epub_id}'
        
        title_elem = ET.SubElement(metadata_elem, 'dc:title')
        title_elem.text = metadata.get('title', 'Unknown Title')
        
        creator_elem = ET.SubElement(metadata_elem, 'dc:creator')
        creator_elem.text = metadata.get('author', 'Unknown Author')
        
        language_elem = ET.SubElement(metadata_elem, 'dc:language')
        language_elem.text = 'en'
        
        modified_elem = ET.SubElement(metadata_elem, 'meta')
        modified_elem.set('property', 'dcterms:modified')
        modified_elem.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Calculate total duration
        total_duration = sum(chapter['duration'] for chapter in chapters)
        
        # Global media overlay metadata
        global_duration_meta = ET.SubElement(metadata_elem, 'meta')
        global_duration_meta.set('property', 'media:duration')
        global_duration_meta.text = format_time(total_duration)
        
        # Individual chapter media overlay metadata
        for i, manifest in enumerate(chapter_manifests):
            chapter_duration = manifest['chapter']['duration']
            duration_meta = ET.SubElement(metadata_elem, 'meta')
            duration_meta.set('property', 'media:duration')
            duration_meta.set('refines', f'#smil_{i+1:03d}')
            duration_meta.text = format_time(chapter_duration)
        
        # Manifest section
        manifest_elem = ET.SubElement(root, 'manifest')
        
        # Add original CSS files if available
        if self.original_epub_data and self.original_epub_data['css_files']:
            for css_name in self.original_epub_data['css_files'].keys():
                css_item = ET.SubElement(manifest_elem, 'item')
                css_item.set('id', f'css_{css_name.replace(".", "_")}')
                css_item.set('href', f'Styles/{css_name}')
                css_item.set('media-type', 'text/css')
        
        # Add our enhanced CSS
        css_item = ET.SubElement(manifest_elem, 'item')
        css_item.set('id', 'css')
        css_item.set('href', 'Styles/style.css')
        css_item.set('media-type', 'text/css')
        
        # Add original images if available
        if self.original_epub_data and self.original_epub_data['images']:
            for img_name in self.original_epub_data['images'].keys():
                img_item = ET.SubElement(manifest_elem, 'item')
                img_item.set('id', f'img_{img_name.replace(".", "_").replace("-", "_")}')
                img_item.set('href', f'Images/{img_name}')
                
                # Determine media type
                ext = img_name.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg']:
                    media_type = 'image/jpeg'
                elif ext == 'png':
                    media_type = 'image/png'
                elif ext == 'gif':
                    media_type = 'image/gif'
                elif ext == 'svg':
                    media_type = 'image/svg+xml'
                else:
                    media_type = 'image/jpeg'  # fallback
                
                img_item.set('media-type', media_type)
                
                # Mark cover image if identified
                if self.original_epub_data.get('cover_image') == img_name:
                    img_item.set('properties', 'cover-image')
        
        # Add navigation
        nav_item = ET.SubElement(manifest_elem, 'item')
        nav_item.set('id', 'nav')
        nav_item.set('href', 'Text/nav.xhtml')
        nav_item.set('media-type', 'application/xhtml+xml')
        nav_item.set('properties', 'nav')
        
        # Add NCX
        ncx_item = ET.SubElement(manifest_elem, 'item')
        ncx_item.set('id', 'ncx')
        ncx_item.set('href', 'toc.ncx')
        ncx_item.set('media-type', 'application/x-dtbncx+xml')
        
        # Add chapters
        for i, manifest in enumerate(chapter_manifests):
            chapter_num = i + 1
            
            # Audio file
            audio_item = ET.SubElement(manifest_elem, 'item')
            audio_item.set('id', f'audio_{chapter_num:03d}')
            audio_item.set('href', f'Audio/{manifest["chapter"]["filename"]}')
            audio_item.set('media-type', 'audio/mpeg')
            
            # XHTML file
            xhtml_item = ET.SubElement(manifest_elem, 'item')
            xhtml_item.set('id', f'xhtml_{chapter_num:03d}')
            xhtml_item.set('href', f'Text/{manifest["xhtml_file"]}')
            xhtml_item.set('media-type', 'application/xhtml+xml')
            xhtml_item.set('media-overlay', f'smil_{chapter_num:03d}')
            
            # SMIL file
            smil_item = ET.SubElement(manifest_elem, 'item')
            smil_item.set('id', f'smil_{chapter_num:03d}')
            smil_item.set('href', f'Text/{manifest["smil_file"]}')
            smil_item.set('media-type', 'application/smil+xml')
        
        # Spine section
        spine_elem = ET.SubElement(root, 'spine')
        spine_elem.set('toc', 'ncx')
        
        for i in range(len(chapter_manifests)):
            itemref = ET.SubElement(spine_elem, 'itemref')
            itemref.set('idref', f'xhtml_{i+1:03d}')
        
        # Write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(oebps_dir / 'content.opf', encoding='utf-8', xml_declaration=True)
    
    def _create_toc_ncx(self, oebps_dir: Path, epub_id: str, metadata: Dict, chapters: List[Dict]):
        """Create toc.ncx navigation file"""
        ncx_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="urn:uuid:{epub_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{metadata.get('title', 'Unknown Title')}</text>
    </docTitle>
    <navMap>
'''
        
        for i, chapter in enumerate(chapters):
            chapter_num = i + 1
            ncx_content += f'''        <navPoint id="navpoint-{chapter_num}" playOrder="{chapter_num}">
            <navLabel>
                <text>{chapter['title']}</text>
            </navLabel>
            <content src="Text/chapter_{chapter_num:03d}.xhtml"/>
        </navPoint>
'''
        
        ncx_content += '''    </navMap>
</ncx>'''
        
        with open(oebps_dir / 'toc.ncx', 'w', encoding='utf-8') as f:
            f.write(ncx_content)
    
    def _create_nav_xhtml(self, text_dir: Path, chapters: List[Dict]):
        """Create EPUB 3 navigation document"""
        nav_content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
    <title>Navigation</title>
    <link rel="stylesheet" href="../Styles/style.css" type="text/css"/>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>Table of Contents</h1>
        <ol>
'''
        
        for i, chapter in enumerate(chapters):
            chapter_num = i + 1
            nav_content += f'            <li><a href="chapter_{chapter_num:03d}.xhtml">{chapter["title"]}</a></li>\n'
        
        nav_content += '''        </ol>
    </nav>
</body>
</html>'''
        
        with open(text_dir / 'nav.xhtml', 'w', encoding='utf-8') as f:
            f.write(nav_content)
    
    def _package_epub(self, epub_dir: Path, output_path: Path) -> Path:
        """Package EPUB directory into ZIP file"""
        self.logger.info(f"Packaging EPUB: {output_path}")
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add mimetype first (uncompressed)
            zf.write(epub_dir / 'mimetype', 'mimetype', compress_type=zipfile.ZIP_STORED)
            
            # Add all other files
            for file_path in epub_dir.rglob('*'):
                if file_path.is_file() and file_path.name != 'mimetype':
                    arc_path = file_path.relative_to(epub_dir)
                    zf.write(file_path, arc_path)
        
        return output_path
    
    def validate_epub(self, epub_path: Path, epubcheck_jar_path: Optional[Path] = None):
        """Validate EPUB using epubcheck if available"""
        
        # Try to find epubcheck jar file
        jar_path = None
        
        if epubcheck_jar_path and epubcheck_jar_path.exists():
            jar_path = epubcheck_jar_path
        else:
            # Try default locations
            possible_paths = [
                Path(__file__).parent.parent / "test-resources" / "epubcheck-5.1.0" / "epubcheck.jar",
                Path.cwd() / "epubcheck.jar",
                Path.cwd() / "test-resources" / "epubcheck-5.1.0" / "epubcheck.jar",
            ]
            
            for path in possible_paths:
                if path.exists():
                    jar_path = path
                    break
        
        if not jar_path:
            self.logger.info("epubcheck not found, skipping validation")
            self.logger.info("To enable validation, provide --epubcheck-jar path or place epubcheck.jar in current directory")
            return
        
        # Check for Java
        if not shutil.which("java"):
            self.logger.warning("Java not found, cannot run epubcheck validation")
            return
        
        try:
            command = ["java", "-jar", str(jar_path), str(epub_path)]
            result = run_command(command, capture_output=False)
            self.logger.info("EPUB validation completed successfully")
        except Exception as e:
            self.logger.warning(f"EPUB validation failed: {e}")
            # Don't raise exception as validation is optional