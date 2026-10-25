import csv
from pathlib import Path
from src.document_loader import load_documents
from src.retriever import Retriever

def build_dataset(tmp_path: Path) -> Path:
    (tmp_path / "kb").mkdir(); (tmp_path / "data").mkdir()
    (tmp_path / "kb" / "policy_current.md").write_text('''---\ndoc_id: POL-X\ntitle: Refund policy\ndoc_type: policy\neffective_from: 2026-01-01\nstatus: current\n---\n# Refund policy\n## [REF-2] Wallet refunds\nWallet refund is instant within two hours.\n''',encoding='utf-8')
    (tmp_path / "kb" / "pol_returns_v3_superseded.md").write_text('''---\ndoc_id: POL-RET-v3\ntitle: Returns policy v3\ndoc_type: policy\neffective_from: 2025-03-01\nstatus: superseded\n---\n## [RETv3-2] Electronics return window\nElectronics had a ten-day return window in version 3.\n''',encoding='utf-8')
    with (tmp_path / "data" / "products.csv").open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['sku','title','price_inr']);w.writeheader();w.writerow({'sku':'ELE-0001','title':'Phone','price_inr':'12000'})
    return tmp_path

def test_superseded_policy_is_conditional_reference_only(tmp_path):
    root=build_dataset(tmp_path)
    docs=load_documents(root)
    assert any(d['section_id']=='REF-2' for d in docs)
    assert any(d['section_id']=='RETv3-2' and d['status']=='superseded' for d in docs)
    r=Retriever(docs)
    ordinary=r.search('What is the current return window for electronics?',top_k=10)
    assert not any(d['status']=='superseded' for d in ordinary)
    legacy=r.search('What was the return window for electronics delivered on 20 July?',top_k=10)
    assert any(d['section_id']=='RETv3-2' and d['status']=='superseded' for d in legacy)

def test_retriever_returns_sources_and_product_record(tmp_path):
    root=build_dataset(tmp_path)
    r=Retriever.from_dataset(root)
    policy=r.search('How fast are wallet refunds?',top_k=3)
    assert policy and policy[0]['section_id']=='REF-2'
    product=r.search('What is the price and warranty for SKU ELE-0001?',top_k=3)
    assert any(d['source']=='products.csv:ELE-0001' for d in product)
