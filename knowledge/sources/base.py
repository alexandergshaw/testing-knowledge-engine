"""Source adapter interface. To add a new knowledge domain, subclass Source
in a new module and add an instance in pipeline.select_sources()."""

import re
from dataclasses import dataclass
from html import unescape

import requests

USER_AGENT = "KnowledgeEngine/1.0 (educational demo; no-LLM retrieval engine)"
REQUEST_TIMEOUT = 6


@dataclass
class Passage:
    text: str
    title: str
    url: str
    source: str       # human-readable source name, e.g. "Wikipedia"
    trust: float      # multiplier applied to BM25 scores for this source


class Source:
    name = "base"
    trust = 1.0

    def search(self, query):
        """query: knowledge.query.AnalyzedQuery -> list[Passage]"""
        raise NotImplementedError

    def get(self, url, params):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def strip_html(html):
    """Plain text from API-returned HTML. Code blocks are dropped (prose is
    what we synthesize), inline code keeps its text."""
    html = re.sub(r"<pre[^>]*>.*?</pre>", " ", html, flags=re.S)
    html = re.sub(r"<blockquote[^>]*>", " ", html)
    html = re.sub(r"<code>(.*?)</code>", r"\1", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()
