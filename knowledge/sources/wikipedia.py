"""Wikipedia and Wiktionary adapters — both speak the MediaWiki API."""

import re

from .base import Passage, Source

MAX_EXTRACT_CHARS = 2000


class MediaWikiSource(Source):
    host = "en.wikipedia.org"
    name = "Wikipedia"
    trust = 1.0
    result_limit = 3
    intro_only = True

    def search(self, query):
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.topic,
            "gsrlimit": self.result_limit,
            "prop": "extracts",
            "explaintext": 1,
            "exlimit": "max",
            "redirects": 1,
            "format": "json",
        }
        if self.intro_only:
            params["exintro"] = 1
        data = self.get(f"https://{self.host}/w/api.php", params)
        pages = data.get("query", {}).get("pages", {})
        passages = []
        # gsr "index" preserves search relevance order
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            text = self.clean(page.get("extract") or "")
            if len(text) < 40:
                continue
            title = page.get("title", "")
            passages.append(
                Passage(
                    text=text[:MAX_EXTRACT_CHARS],
                    title=title,
                    url=f"https://{self.host}/wiki/{title.replace(' ', '_')}",
                    source=self.name,
                    trust=self.trust,
                )
            )
        return passages

    def clean(self, text):
        return re.sub(r"\s+", " ", text).strip()


class WikipediaSource(MediaWikiSource):
    pass


class WiktionarySource(MediaWikiSource):
    host = "en.wiktionary.org"
    name = "Wiktionary"
    trust = 0.85
    result_limit = 1
    intro_only = False  # Wiktionary entries have empty intros; content lives in sections

    _POS_SECTION = re.compile(
        r"===\s*(?:Noun|Proper noun|Verb|Adjective|Adverb|Phrase|Interjection)\s*===\s*"
        r"(.*?)(?:\n=|$)",
        flags=re.S,
    )

    def clean(self, text):
        # Keep only the English section, then only part-of-speech definition
        # sections (drops etymology, pronunciation, translations).
        match = re.search(r"==\s*English\s*==(.*?)(?:\n==[^=]|$)", text, flags=re.S)
        if match:
            text = match.group(1)
        definitions = self._POS_SECTION.findall(text)
        if definitions:
            text = " ".join(definitions)
        else:
            text = re.sub(r"=+[^=]+=+", " ", text)
        return re.sub(r"\s+", " ", text).strip()
