from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solosophy_engine import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SoloSophy research pipeline")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw" / "refresh_2026_09_07")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "audited")
    parser.add_argument('--as-of', help='Explicit UTC as-of timestamp for reproducible research replay')
    args = parser.parse_args()
    result = run_pipeline(args.raw_dir, args.output_dir, as_of=args.as_of)
    print(f"Pipeline complete. Assets: {', '.join(sorted(result['timeframe_states']))}")


if __name__ == "__main__":
    main()
