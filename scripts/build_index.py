from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import Settings
from src.retriever import Retriever

def main():
    p = argparse.ArgumentParser(description="Build the persisted ZentroMart TF-IDF vector index.")
    p.add_argument("--dataset-dir", type=Path, default=None, help="Extracted challenge dataset directory (defaults to DATASET_DIR).")
    p.add_argument("--output", type=Path, default=None, help="Index output (defaults to VECTOR_STORE_PATH).")
    args = p.parse_args()
    settings = Settings.from_env()
    dataset = (args.dataset_dir or settings.dataset_dir).resolve()
    if not dataset.exists():
        p.error(f"Dataset directory not found: {dataset}. Extract the supplied ZIP and set DATASET_DIR.")
    output = args.output or settings.vector_store_path
    retriever = Retriever.from_dataset(dataset)
    retriever.save(output)
    print(f"Index built: {len(retriever.documents)} chunks/records -> {output}")
    print("Superseded policy text is filtered from ordinary searches and retained only for explicitly preserved legacy cases.")

if __name__ == "__main__": main()
