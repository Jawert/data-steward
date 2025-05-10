from pathlib import Path
from langchain_community.llms import Ollama
import pdfplumber
import os
from collections import defaultdict
import re

class PDFAnalyzer:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path
        self.llm = Ollama(model="mistral")

    def list_pdfs(self) -> list[str]:
        """List all PDF files in a folder"""
        return [
            os.path.join(self.folder_path, f.name)
            for f in Path(self.folder_path).iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"
        ]
    
    def extract_pdf_text(self, pdf_path: str) -> dict:
        """
        Enhanced generic PDF text extraction with structural analysis and metadata.
        
        This function extracts text from any type of PDF with additional contextual information:
        - Headers/footers detection
        - Table content identification
        - Font size analysis for heading detection
        - Image placement information
        - Basic layout analysis
        - Date detection
        - Named entity recognition
        - Keyword extraction
        """
        
        
        text_by_page = []
        full_text = ""
        tables_data = []
        metadata = {
            "filename": os.path.basename(pdf_path),
            "filesize": os.path.getsize(pdf_path),
            "creation_date": None,
            "modification_date": None,
            "page_count": 0,
            "has_tables": False,
            "has_images": False,
            "potential_dates": [],
            "potential_amounts": [],
            "named_entities": set(),
            "potential_keywords": set()
        }
        
        # Regular expressions for detecting important information
        date_patterns = [
            r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b',  # MM/DD/YYYY
            r'\b(?:19|20)\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])\b',  # YYYY/MM/DD
            r'\b(?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:19|20)\d{2}\b',  # DD/MM/YYYY
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?,? (?:19|20)\d{2}\b'  # Month DD, YYYY
        ]
        
        # Generalized numeric patterns (for various types of documents)
        numeric_patterns = [
            r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b',  # Numbers with decimals
            r'\b\d+\b'  # Simple numbers
        ]
        
        # Generic entity pattern for identifying potential named entities
        entity_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Proper nouns/names
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b(?:ID|Number|Reference):\s*([A-Z0-9-]+)\b'  # Common identifiers
        ]
        
        with pdfplumber.open(pdf_path) as pdf:
            # Extract PDF metadata
            if pdf.metadata:
                metadata["creation_date"] = pdf.metadata.get('CreationDate')
                metadata["modification_date"] = pdf.metadata.get('ModDate')
            
            metadata["page_count"] = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                
                # Extract images data
                images = page.images
                if images:
                    metadata["has_images"] = True
                
                image_data = []
                for img in images:
                    image_data.append({
                        "bbox": (img["x0"], img["top"], img["x1"], img["bottom"]),
                        "width": img["width"],
                        "height": img["height"]
                    })
                
                # Extract tables
                tables = page.extract_tables()
                page_tables = []
                
                if tables:
                    metadata["has_tables"] = True
                    for t_idx, table in enumerate(tables):
                        # Convert None values to empty strings and join cells
                        clean_table = []
                        for row in table:
                            clean_row = []
                            for cell in row:
                                if cell is not None:
                                    clean_row.append(cell.strip())
                                else:
                                    clean_row.append("")
                            clean_table.append(clean_row)
                        
                        page_tables.append({
                            "table_idx": t_idx,
                            "data": clean_table
                        })
                        tables_data.append({
                            "page": page_num,
                            "table_idx": t_idx,
                            "data": clean_table
                        })
                
                # Get text with font information
                words_with_font = []
                if hasattr(page, "extract_words") and callable(page.extract_words):
                    words = page.extract_words(extra_attrs=["fontname", "size"])
                    for word in words:
                        words_with_font.append({
                            "text": word["text"],
                            "font": word.get("fontname", ""),
                            "size": word.get("size", 0),
                            "position": (word["x0"], word["top"], word["x1"], word["bottom"])
                        })
                
                # Identify potential headers and footers
                page_height = page.height
                page_width = page.width
                
                header_zone_height = page_height * 0.15  # Top 15% of page
                footer_zone_height = page_height * 0.15  # Bottom 15% of page
                
                header_text = ""
                body_text = ""
                footer_text = ""
                
                # Extract text with position information
                text = page.extract_text() or ""
                lines = text.splitlines()
                
                # Analyze text lines with their vertical positions
                chars = page.chars
                if chars:
                    lines_with_position = []
                    current_line = []
                    current_y = chars[0]["top"]
                    line_height_threshold = 3  # Adjust based on your PDFs
                    
                    for char in chars:
                        if abs(char["top"] - current_y) > line_height_threshold:
                            # New line detected
                            if current_line:
                                text = "".join([c["text"] for c in current_line])
                                y_pos = sum([c["top"] for c in current_line]) / len(current_line)
                                lines_with_position.append((text, y_pos))
                                current_line = []
                            current_y = char["top"]
                        current_line.append(char)
                    
                    # Add the last line
                    if current_line:
                        text = "".join([c["text"] for c in current_line])
                        y_pos = sum([c["top"] for c in current_line]) / len(current_line)
                        lines_with_position.append((text, y_pos))
                    
                    # Categorize lines into header, body, and footer
                    for line_text, y_pos in lines_with_position:
                        if y_pos <= header_zone_height:
                            header_text += line_text + "\n"
                        elif y_pos >= (page_height - footer_zone_height):
                            footer_text += line_text + "\n"
                        else:
                            body_text += line_text + "\n"
                else:
                    # Fallback if character-level data isn't available
                    body_text = text
                
                # Clean all texts
                header_text = "\n".join(line.strip() for line in header_text.splitlines() if line.strip())
                body_text = "\n".join(line.strip() for line in body_text.splitlines() if line.strip())
                footer_text = "\n".join(line.strip() for line in footer_text.splitlines() if line.strip())
                
                # Find potential dates, numbers, and entities
                all_text = text
                for pattern in date_patterns:
                    dates = re.findall(pattern, all_text)
                    if dates:
                        metadata["potential_dates"].extend(dates)
                
                for pattern in numeric_patterns:
                    numbers = re.findall(pattern, all_text)
                    if numbers:
                        metadata["potential_amounts"].extend(numbers)
                
                for pattern in entity_patterns:
                    entities = re.findall(pattern, all_text)
                    if entities:
                        for entity in entities:
                            if isinstance(entity, tuple):  # Handle capture groups
                                entity = entity[0]
                            if entity and len(entity.strip()) > 1:  # Filter out single characters
                                metadata["named_entities"].add(entity.strip())
                
                # Store the analyzed data for this page
                page_data = {
                    "page_number": page_num,
                    "header": header_text,
                    "body": body_text,
                    "footer": footer_text,
                    "full_text": text,
                    "tables": page_tables,
                    "images": image_data,
                    "font_analysis": words_with_font
                }
                text_by_page.append(page_data)
                
                # Add to full text with structural markers
                full_text += f"\n\n--- PAGE {page_num} ---\n"
                if header_text:
                    full_text += f"[HEADER]\n{header_text}\n[/HEADER]\n\n"
                full_text += f"[BODY]\n{body_text}\n[/BODY]\n\n"
                if footer_text:
                    full_text += f"[FOOTER]\n{footer_text}\n[/FOOTER]\n"
                if page_tables:
                    full_text += f"\n[TABLES]\n"
                    for table_data in page_tables:
                        full_text += f"Table {table_data['table_idx'] + 1}:\n"
                        for row in table_data['data']:
                            full_text += " | ".join(row) + "\n"
                    full_text += f"[/TABLES]\n"
        
        # Clean up metadata
        metadata["potential_dates"] = list(set(metadata["potential_dates"]))
        metadata["potential_amounts"] = list(set(metadata["potential_amounts"]))
        metadata["named_entities"] = list(metadata["named_entities"])
        
        # Extract potential keywords (frequent words that aren't stopwords)
        stopwords = set(['a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 
                        'when', 'where', 'how', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                        'have', 'has', 'had', 'do', 'does', 'did', 'to', 'from', 'in', 'out',
                        'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
                        'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
                        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
                        'too', 'very', 's', 't', 'can', 'will', 'just', 'should', 'now', 'i',
                        'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
                        'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she',
                        'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their',
                        'theirs', 'themselves', 'this', 'that', 'these', 'those', 'of', 'for', 'by'])
        
        # Find word frequencies in all text
        word_pattern = re.compile(r'\b[a-z]{3,}\b', re.IGNORECASE)
        words = word_pattern.findall(full_text.lower())
        word_counts = {}
        
        for word in words:
            if word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get top keywords (words that appear multiple times)
        keywords = sorted([(count, word) for word, count in word_counts.items() if count > 1], reverse=True)[:10]
        metadata["potential_keywords"] = set([word for _, word in keywords])
        
        # Create a summary section
        summary = []
        if metadata["potential_dates"]:
            summary.append(f"Dates found: {', '.join(metadata['potential_dates'][:5])}")
        if metadata["potential_amounts"]:
            summary.append(f"Numbers found: {', '.join(metadata['potential_amounts'][:5])}")
        if metadata["named_entities"]:
            summary.append(f"Entities found: {', '.join(list(metadata['named_entities'])[:5])}")
        if metadata["potential_keywords"]:
            summary.append(f"Keywords found: {', '.join(metadata['potential_keywords'])}")
        
        return {
            "full_text": full_text.strip(),
            "structured_text": text_by_page,
            "tables": tables_data,
            "metadata": metadata,
            "summary": "\n".join(summary)
        }

    def analyze(self, pdf_path: str) -> str:
        """Analyze a PDF file and return a suggested name."""
        content = self.extract_pdf_text(pdf_path)
        prompt = """
            You are DataSteward, an AI assistant specialized in analyzing documents and suggesting organized filenames.

            When analyzing any document:
            1. Identify the document type (invoice, payment confirmation, report, letter, etc.)
            2. Extract the most relevant date (payment date, issue date, due date)
            3. Identify key entities (companies, institutions)
            4. Identify monetary amounts when relevant

            For payment documents:
            - Format: "YYYY-MM-DD Payment to [Recipient].pdf"
            - Example: "2024-03-15 Student Loan Payment to Nelnet.pdf"

            For other document types:
            - Format: "YYYY-MM-DD [Document Type] - [Key Subject].pdf"
            - Example: "2024-05-10 Invoice - Home Insurance.pdf"

            If a date is unavailable, omit it from the filename.
            If an amount is unavailable for payment documents, omit it.
            Keep filenames concise, descriptive, and under 60 characters.
            Use only alphanumeric characters, hyphens, underscores, and spaces.

            Reply with only the suggested filename, nothing else.

            """
        
        result = self.llm.invoke(prompt + "\n\n" + content["full_text"])
        return result.strip()    