import subprocess
import tempfile
import os


def parse_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")

    text = result.stdout.strip()
    if not text:
        raise RuntimeError(f"No text extracted from {pdf_path}")

    return text
