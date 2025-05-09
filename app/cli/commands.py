import click
import os
from app.services.pdf_analyzer import PDFAnalyzer

@click.group()
def cli():
    pass

@cli.command()
def hello():
    """Data Steward - your local AI file organization tool"""
    click.echo("Hello, Data Steward!")

@cli.command()
@click.argument("folder", type=click.Path(exists=True))
def analyze_folder(folder):
    """Analyze a folder of PDFs"""
    folder = os.path.expanduser(folder)
    pdfs = PDFAnalyzer(folder).list_pdfs()
    click.echo(pdfs)