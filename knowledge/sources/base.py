"""Source adapter interface. To add a new knowledge domain, subclass Source
in a new module and add an instance in pipeline.select_sources()."""

import re
import threading
import time
from dataclasses import dataclass, field
from html import unescape

import requests

USER_AGENT = "KnowledgeEngine/1.0 (educational demo; no-LLM retrieval engine)"
REQUEST_TIMEOUT = 6
MAX_RETRY_AFTER_SECONDS = 5
MIN_REQUEST_INTERVAL = 0.15  # global politeness throttle across all sources

# Shared keep-alive session: fewer connections is both faster and politer to
# the public APIs.
_session = requests.Session()
_throttle_lock = threading.Lock()
_last_request_time = 0.0


def _throttle():
    global _last_request_time
    with _throttle_lock:
        wait = _last_request_time + MIN_REQUEST_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.monotonic()


@dataclass
class Passage:
    text: str
    title: str
    url: str
    source: str       # human-readable source name, e.g. "Wikipedia"
    trust: float      # multiplier applied to BM25 scores for this source
    code: list = field(default_factory=list)  # verbatim code blocks, for examples


class Source:
    name = "base"
    trust = 1.0

    def search(self, query):
        """query: knowledge.query.AnalyzedQuery -> list[Passage]"""
        raise NotImplementedError

    def get(self, url, params):
        for attempt in (1, 2):
            _throttle()
            response = _session.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 429 and attempt == 1:
                try:
                    delay = float(response.headers.get("Retry-After", 2))
                except ValueError:
                    delay = 2.0
                time.sleep(min(delay, MAX_RETRY_AFTER_SECONDS))
                continue
            response.raise_for_status()
            return response.json()


def strip_html(html):
    """Plain text from API-returned HTML. Code blocks are dropped (prose is
    what we synthesize), inline code keeps its text. Block-element boundaries
    become sentence breaks so headings don't glue onto the next paragraph."""
    html = re.sub(r"<pre[^>]*>.*?</pre>", ". ", html, flags=re.S)
    html = re.sub(r"<code>(.*?)</code>", r"\1", html, flags=re.S)
    html = re.sub(r"</(p|h[1-6]|li|blockquote|tr|div)>|<br\s*/?>", ". ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    text = unescape(html)
    # A colon that introduced a removed code block ends its sentence —
    # otherwise "accumulate decorators:" glues onto the next paragraph.
    text = re.sub(r":\s*(\.\s*)+", ". ", text)
    # Drop the periods we injected right after existing punctuation.
    text = re.sub(r"([.!?;,])(\s*\.)+", r"\1 ", text)
    text = re.sub(r"(\s*\.){2,}", ". ", text)
    return re.sub(r"\s+", " ", text).strip()
