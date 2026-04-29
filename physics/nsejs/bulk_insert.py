"""
Bulk-insert all per-year nsejs_<YYYY>_<YY>_classified.json files into
physics_practice.db. Wraps insert_questions.main() per year.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from physics.nsejs.insert_questions import main as insert_main


HERE = Path(__file__).parent


def main():
    files = sorted(HERE.glob('nsejs_*_classified.json'))
    print(f'Found {len(files)} per-year classified files')
    for f in files:
        # filename: nsejs_2010_11_classified.json -> paper_id="2010_11", year=2010
        stem = f.stem  # nsejs_2010_11_classified
        parts = stem.split('_')
        if len(parts) != 4:
            print(f'skip (unexpected name): {f.name}')
            continue
        _, yyyy, yy, _ = parts
        paper_id = f'{yyyy}_{yy}'
        year = int(yyyy)
        label = f'NSEJS {yyyy}-{yy}'
        print(f'\n=== {label} ({f.name}) ===')
        try:
            insert_main(paper_id, year, label)
        except Exception as e:
            print(f'  FAILED: {e}')


if __name__ == '__main__':
    main()
