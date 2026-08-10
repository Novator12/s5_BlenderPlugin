from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
HANDBOOK_DIR = SCRIPT_PATH.parents[1]
DEPS_DIR = HANDBOOK_DIR / "_deps"
sys.path.insert(0, str(DEPS_DIR))

import pymupdf
from pypdf import PdfReader


DEFAULT_PDF_PATH = HANDBOOK_DIR / "Settlers_5_Blender_Plugin_Handbook_EN.pdf"
DEFAULT_RENDER_DIR = HANDBOOK_DIR / "_rendered_pdf"
DEFAULT_AUDIT_PATH = HANDBOOK_DIR / "pdf_audit.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument("--render-dir", type=Path, default=DEFAULT_RENDER_DIR)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()
    pdf_path = args.pdf.resolve()
    render_dir = args.render_dir.resolve()
    audit_path = args.audit.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"Missing PDF: {pdf_path}")
    if render_dir.exists():
        shutil.rmtree(render_dir)
    render_dir.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open(pdf_path)
    pages = []
    for index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.65, 1.65), alpha=False)
        output = render_dir / f"page-{index + 1:03d}.png"
        pixmap.save(output)
        page_text = page.get_text("text")
        try:
            render_reference = output.relative_to(HANDBOOK_DIR)
        except ValueError:
            render_reference = output
        pages.append(
            {
                "page": index + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "text_characters": len(page_text),
                "image_count": len(page.get_images(full=True)),
                "render": str(render_reference),
            }
        )
    document.close()

    reader = PdfReader(str(pdf_path))
    metadata = {str(key): str(value) for key, value in (reader.metadata or {}).items()}
    extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    expected_terms = [
        "Blender 5.0.1",
        "Novator12",
        "Bounding sphere",
        "Clear Scene",
        "NumBones",
        "S5Converter",
        "RenderWare",
    ]
    audit = {
        "pdf": str(pdf_path),
        "bytes": pdf_path.stat().st_size,
        "page_count": len(pages),
        "metadata": metadata,
        "outline_present": bool(reader.outline),
        "total_extracted_characters": len(extracted_text),
        "missing_expected_terms": [
            term for term in expected_terms if term.casefold() not in extracted_text.casefold()
        ],
        "pages": pages,
    }
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
