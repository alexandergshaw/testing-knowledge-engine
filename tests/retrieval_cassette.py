"""Record/replay for source HTTP responses, so the retrieval-quality benchmark
runs offline and deterministically.

Capture happens at the single network entry point — `Source.get(url, params)` —
keyed by a stable hash of (url, params). Recording hits the real APIs once
(scripts/record_retrieval_fixtures.py); replay monkeypatches `Source.get` to
return the recorded JSON, so the full real pipeline (search -> rank ->
synthesize) runs against fixed inputs.
"""

import hashlib
import json
from urllib.parse import urlencode

from knowledge.sources import base

CASSETTE_PATH = "tests/fixtures/retrieval/cassette.json"


def key(url, params):
    blob = url + "?" + urlencode(sorted((params or {}).items()))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def load(path=CASSETTE_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def install_recorder(cassette):
    """Wrap Source.get to record every response into `cassette`. Returns a
    restore() callable."""
    original = base.Source.get

    def recording_get(self, url, params):
        response = original(self, url, params)
        cassette[key(url, params)] = response
        return response

    base.Source.get = recording_get
    return lambda: setattr(base.Source, "get", original)


def install_replay(cassette, monkeypatch):
    """Monkeypatch Source.get to replay from `cassette`; a missing entry raises
    (so an un-recorded call is loud), which fetch() catches per-source."""

    def replay_get(self, url, params):
        entry = cassette.get(key(url, params))
        if entry is None:
            raise RuntimeError(f"no cassette entry for {url} {params}")
        return entry

    monkeypatch.setattr(base.Source, "get", replay_get)
