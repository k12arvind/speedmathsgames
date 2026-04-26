#!/usr/bin/env python3
"""Build the AMC 10 question bank database from local PDFs."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amc10.db import AMC10Database
from amc10.parser import import_amc10_folder


def main() -> None:
    root = ROOT
    folder = root / "AMC10 Practice Papers"
    db = AMC10Database(str(root / "amc10_practice.db"))
    result = import_amc10_folder(folder, db)
    print(f"Imported {result['contests_imported']} contests and {result['questions_imported']} questions into {root / 'amc10_practice.db'}")


if __name__ == "__main__":
    main()
