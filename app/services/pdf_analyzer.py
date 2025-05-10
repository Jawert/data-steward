from pathlib import Path
from langchain_community.llms import Ollama
import pdfplumber
import os

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
        text_by_page = []
        full_text = ""

        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                text = "\n".join(line.strip() for line in text.splitlines() if line.strip())  # Clean whitespace
                text_by_page.append({
                    "page_number": i + 1,
                    "text": text
                })
                full_text += f"\n--- Page {i + 1} ---\n{text}"

        return {
            "full_text": full_text.strip(),
            "pages": text_by_page,
            "metadata": {
                "page_count": len(text_by_page)
            }
        }

    def analyze(self, pdf_path: str) -> str:
        """Analyze a PDF file and return a suggested name."""
        content = self.extract_pdf_text(pdf_path)
        prompt = """
            You are FileOrganizer, an AI assistant specialized in analyzing documents and suggesting organized filenames.

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