from pathlib import Path

class PDFAnalyzer:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def analyze(self):
        """Analyze a folder of PDFs"""
        # TODO: Implement PDF analysis logic
        pass    

    def list_pdfs(self) -> list[str]:
        """List all PDF files in a folder"""
        return [
            f.name
            for f in Path(self.folder_path).iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"
        ]