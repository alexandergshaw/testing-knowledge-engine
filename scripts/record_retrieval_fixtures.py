"""Record real source responses for the retrieval-quality benchmark into a
committed cassette, so the benchmark runs offline. Hits the network — run
manually to (re)create fixtures:

    python -m scripts.record_retrieval_fixtures

Refresh periodically; the recorded JSON lives at tests/fixtures/retrieval/.
"""

import json
import pathlib

from tests.retrieval_cassette import CASSETTE_PATH, install_recorder
from tests.retrieval_eval import run_case
from tests.retrieval_eval_cases import ALL_CASES


def main():
    path = pathlib.Path(CASSETTE_PATH)
    # Merge into any existing cassette so partial (rate-limited) runs accumulate
    # rather than clobber.
    cassette = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    restore = install_recorder(cassette)
    try:
        for case in ALL_CASES:
            objective = case["objective"]
            try:
                run_case(case)  # same path (incl. domain routing) the benchmark replays
                print(f"recorded: {objective}")
            except Exception as error:  # noqa: BLE001 - best-effort recording
                print(f"WARN {objective}: {error}")
    finally:
        restore()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cassette, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {len(cassette)} entries -> {path}")


if __name__ == "__main__":
    main()
