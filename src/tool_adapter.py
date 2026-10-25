"""Adapter that loads the challenge's supplied tools without reimplementing them."""
from __future__ import annotations
import csv
import importlib.util
import re
from pathlib import Path
from types import ModuleType

class ToolConfigurationError(RuntimeError):
    pass

class ChallengeTools:
    def __init__(self, dataset_dir: Path, module: ModuleType | None = None):
        self.dataset_dir = dataset_dir.resolve()
        if module is not None:
            self.module = module
            return
        tool_file = self.dataset_dir / "tools" / "tools.py"
        if not tool_file.is_file():
            raise ToolConfigurationError(f"Supplied challenge tool not found: {tool_file}")
        spec = importlib.util.spec_from_file_location("zentromart_challenge_tools", tool_file)
        if spec is None or spec.loader is None:
            raise ToolConfigurationError("Unable to load the supplied challenge tools module.")
        module_obj = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module_obj)
        except Exception as exc:
            raise ToolConfigurationError("Unable to initialize the supplied challenge tools. Check DATASET_DIR.") from exc
        self.module = module_obj

    def lookup_order(self, order_id: str, verification_value: str | None = None) -> dict:
        return self.module.lookup_order(order_id, verification_value=verification_value)

    def create_ticket(self, summary: str, order_id: str | None = None,
                      reason: str | None = None, intent: str | None = None) -> dict:
        return self.module.create_ticket(summary, order_id=order_id, reason=reason, intent=intent)

    def lookup_ticket(self, ticket_id: str) -> dict:
        """Retrieve an existing ticket from the supplied tool's CSV log.

        This is deliberately read-only: it never creates a ticket and does not
        infer assignment or resolution status that the supplied schema lacks.
        """
        requested = str(ticket_id or "").strip()
        if not re.fullmatch(r"TKT[0-9a-f]{32}", requested, re.IGNORECASE):
            return {"found": False, "reason": "invalid_ticket_id"}

        configured_path = getattr(self.module, "_TICKETS", None)
        if not configured_path:
            raise ToolConfigurationError("The supplied ticket log is not configured.")
        path = Path(configured_path)
        if not path.is_absolute():
            path = (self.dataset_dir / path).resolve()
        if not path.is_file():
            return {"found": False, "reason": "ticket_log_missing"}

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    saved_id = str(row.get("ticket_id") or "").strip()
                    if saved_id.casefold() == requested.casefold():
                        return {"found": True, **row}
        except OSError as exc:
            raise ToolConfigurationError("The saved ticket log could not be read.") from exc

        return {"found": False, "reason": "ticket_not_found"}

