from __future__ import annotations

import json
from pathlib import Path

from eft_scan.index_store import json_to_sqlite, search_sqlite


def test_sqlite_search_exact_prefix_and_id(tmp_path: Path) -> None:
    payload = {
        "15": "Buhaus",
        "6976458": "PoeBwo-TTV",
        "1": "Nikita",
        "2": "NikitaTTV",
    }
    json_path = tmp_path / "index.json"
    sqlite_path = tmp_path / "index.sqlite"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    assert json_to_sqlite(json_path, sqlite_path) == 4

    exact = search_sqlite(sqlite_path, "PoeBwo-TTV")
    assert exact[0].account_id == "6976458"
    assert exact[0].exact

    by_id = search_sqlite(sqlite_path, "6976458")
    assert by_id[0].nickname == "PoeBwo-TTV"

    prefix = search_sqlite(sqlite_path, "Nik")
    assert {item.nickname for item in prefix} == {"Nikita", "NikitaTTV"}

    case = search_sqlite(sqlite_path, "poebwo-ttv")
    assert case[0].account_id == "6976458"
