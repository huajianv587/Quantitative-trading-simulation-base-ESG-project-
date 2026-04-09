from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_docx_text(path: Path) -> str:
    document_xml = zipfile.ZipFile(path).read("word/document.xml")
    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:p", WORD_NAMESPACE):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)

    return "\n".join(paragraphs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from a DOCX file.")
    parser.add_argument("path", type=Path, help="Path to the .docx file")
    parser.add_argument("--output", type=Path, help="Optional path to save extracted text")
    args = parser.parse_args()

    content = extract_docx_text(args.path)
    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(f"saved: {args.output}")
        return
    print(content)


if __name__ == "__main__":
    main()
