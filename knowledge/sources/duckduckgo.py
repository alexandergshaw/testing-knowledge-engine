"""DuckDuckGo Instant Answer API — free abstracts sourced from curated
references (Wikipedia, official docs, encyclopedias)."""

from .base import Passage, Source


class DuckDuckGoSource(Source):
    name = "DuckDuckGo"
    trust = 0.8

    def search(self, query):
        data = self.get(
            "https://api.duckduckgo.com/",
            {
                "q": query.topic,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
                "no_redirect": 1,
            },
        )
        passages = []
        abstract = (data.get("AbstractText") or "").strip()
        if len(abstract) >= 40:
            passages.append(
                Passage(
                    text=abstract,
                    title=data.get("Heading") or query.topic,
                    url=data.get("AbstractURL") or "https://duckduckgo.com",
                    source=data.get("AbstractSource") or self.name,
                    trust=self.trust,
                )
            )
        for topic in self._flatten(data.get("RelatedTopics", []))[:3]:
            text = (topic.get("Text") or "").strip()
            if len(text) < 60:
                continue
            passages.append(
                Passage(
                    text=text,
                    title=text.split(" - ")[0][:80],
                    url=topic.get("FirstURL") or "https://duckduckgo.com",
                    source=self.name,
                    trust=self.trust * 0.85,
                )
            )
        return passages

    def _flatten(self, related):
        flat = []
        for entry in related:
            if "Topics" in entry:
                flat.extend(entry["Topics"])
            else:
                flat.append(entry)
        return flat
