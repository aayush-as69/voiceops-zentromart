"""Markdown front-matter and section-aware document ingestion."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

DOC_TYPE_PRIORITY = {
    "policy": 5,
    "agent_guide": 4,
    "help": 3,
    "faq": 2,
    "marketing": 1,
    "meta": 4,
}


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip().strip('"\'')
            body = parts[2].lstrip()
    return meta, body


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split by headings carrying [SECTION-ID], keeping heading content in section."""
    sections: list[tuple[str, str]] = []
    current_id = "INTRO"
    current_lines: list[str] = []
    pattern = re.compile(r"^#{1,4}\s+\[([^\]]+)\]\s*(.*)$")
    for line in body.splitlines():
        match = pattern.match(line)
        if match:
            previous = "\n".join(current_lines).strip()
            if previous:
                sections.append((current_id, previous))
            current_id = match.group(1).strip()
            heading = line.strip()
            current_lines = [heading]
        else:
            current_lines.append(line)
    previous = "\n".join(current_lines).strip()
    if previous:
        sections.append((current_id, previous))
    return sections


def chunk_section(text: str, max_chars: int = 1250) -> list[str]:
    """Chunk long sections on paragraph boundaries; avoid sentence-level policy splits."""
    if len(text) <= max_chars:
        return [text]
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current = candidate
        if len(current) > max_chars:
            # Rare oversized table/paragraph: split by lines, retaining adjacent rows as much as possible.
            lines = current.splitlines()
            buf = ""
            for line in lines:
                if buf and len(buf) + len(line) + 1 > max_chars:
                    chunks.append(buf.strip())
                    buf = line
                else:
                    buf = f"{buf}\n{line}".strip()
            current = buf
    if current.strip():
        chunks.append(current.strip())
    return chunks


def load_knowledge_documents(dataset_dir: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted((dataset_dir / "kb").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        status = meta.get("status", "unknown").lower()
        # Retain superseded chunks as conditional references; Retriever excludes them unless
        # a current successor explicitly preserves an old-policy scenario.
        doc_type = meta.get("doc_type", "unknown").lower()
        for section_id, section_text in split_sections(body):
            for chunk_i, text in enumerate(chunk_section(section_text)):
                docs.append({
                    "text": text,
                    "source": path.name,
                    "source_path": f"kb/{path.name}",
                    "doc_id": meta.get("doc_id", path.stem),
                    "title": meta.get("title", path.stem),
                    "doc_type": doc_type,
                    "status": status,
                    "effective_from": meta.get("effective_from", ""),
                    "version": meta.get("version", ""),
                    "section_id": section_id,
                    "chunk_index": chunk_i,
                    "priority": DOC_TYPE_PRIORITY.get(doc_type, 0),
                    "authority": doc_type == "policy" and status == "current",
                })
    return docs


def load_product_documents(dataset_dir: Path) -> list[dict[str, Any]]:
    import csv
    path = dataset_dir / "data" / "products.csv"
    products = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sku = row.get("sku", "").strip()
            if not sku:
                continue
            fields = [f"{k.replace('_', ' ')}: {v}" for k, v in row.items() if v not in (None, "")]
            products.append({
                "text": "Product catalog record. " + ". ".join(fields),
                "source": f"products.csv:{sku}",
                "source_path": "data/products.csv",
                "doc_id": f"PRODUCT-{sku}",
                "title": f"Product {sku}",
                "product_title": row.get("title", ""),
                "doc_type": "catalog",
                "status": "current",
                "effective_from": "",
                "version": "",
                "section_id": sku,
                "chunk_index": 0,
                "priority": 3,
                "authority": True,
            })
    return products


def load_documents(dataset_dir: Path) -> list[dict[str, Any]]:
    return load_knowledge_documents(dataset_dir) + load_product_documents(dataset_dir)
