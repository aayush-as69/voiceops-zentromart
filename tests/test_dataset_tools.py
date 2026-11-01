"""Integration smoke tests against the supplied dataset, enabled with DATASET_DIR."""
import csv, os, shutil
from pathlib import Path
import pytest
from src.tool_adapter import ChallengeTools

@pytest.mark.skipif(not os.getenv('DATASET_DIR'), reason='Set DATASET_DIR to run supplied-dataset integration tests')
def test_supplied_order_tool_withholds_unverified_details(tmp_path):
    root=Path(os.environ['DATASET_DIR']).resolve()
    # Work on an isolated copy because create_ticket writes into the tools folder.
    clone=tmp_path/'dataset'
    shutil.copytree(root,clone,ignore=shutil.ignore_patterns('tickets_created.csv','__pycache__'))
    tools=ChallengeTools(clone)
    pending=tools.lookup_order('8978 2837')
    assert pending.get('verification_required') is True
    assert 'status' not in pending and 'items' not in pending
    verified=tools.lookup_order('89782837',verification_value='4533')
    assert verified.get('verified') is True and verified.get('found') is True


@pytest.mark.skipif(not os.getenv('DATASET_DIR'), reason='Set DATASET_DIR to run supplied-dataset integration tests')
def test_supplied_ticket_creation_is_persisted_and_can_be_read_back(tmp_path):
    root = Path(os.environ['DATASET_DIR']).resolve()
    clone = tmp_path / 'dataset'
    shutil.copytree(root, clone, ignore=shutil.ignore_patterns('tickets_created.csv', '__pycache__'))
    tools = ChallengeTools(clone)

    created = tools.create_ticket(
        summary='Synthetic test escalation: review delayed shipment and advise customer.',
        order_id='69520867', reason='customer_requested_human', intent='delivery_delay',
    )
    assert created.get('created') is True
    ticket_id = created['ticket_id']
    ticket_path = clone / 'tools' / 'tickets_created.csv'
    assert ticket_path.is_file()
    with ticket_path.open(encoding='utf-8', newline='') as handle:
        saved_rows = list(csv.DictReader(handle))
    assert any(row.get('ticket_id') == ticket_id for row in saved_rows)

    retrieved = tools.lookup_ticket(ticket_id)
    assert retrieved.get('found') is True
    assert retrieved.get('ticket_id') == ticket_id
    assert retrieved.get('order_id') == '69520867'
    assert retrieved.get('reason') == 'customer_requested_human'
    assert retrieved.get('summary') == 'Synthetic test escalation: review delayed shipment and advise customer.'
