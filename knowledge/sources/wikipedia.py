"""Wikipedia, Wikiversity, and Wiktionary adapters — all speak the MediaWiki API."""

import re

from .base import Passage, Source

MAX_EXTRACT_CHARS = 2000

# List harvesting: runs of short link-like lines (outlines, course lesson
# lists, tables of contents) get collapsed into one synthesizable sentence.
LIST_MIN_RUN = 4
LIST_MAX_LINE_CHARS = 60
LIST_MAX_ITEMS = 30
LIST_SENTENCE_MAX_CHARS = 480

# Only sections that plausibly enumerate content topics. Without this filter
# the harvester happily turns "Notable alumni" into "covers topics including:
# Seth Frankoff, MLB pitcher, ...".
_TOPIC_HEADING = re.compile(
    r"lesson|topic|content|outline|syllabus|curriculum|chapter|unit|module|concept",
    re.IGNORECASE,
)
_HEADING_LINE = re.compile(r"^=+\s*(.*?)\s*=+$")


def harvest_list(text, title):
    """Find the longest run of consecutive short non-prose lines under a
    curriculum-shaped heading and turn it into a single citable sentence:
    '<title> covers topics including: ...'."""
    # "Outline of X" pages are topical guides — every section qualifies.
    whole_page_ok = title.lower().startswith("outline of")
    runs, current, heading_ok = [], [], False
    for raw_line in text.split("\n") + [""]:
        stripped_line = raw_line.strip()
        heading = _HEADING_LINE.match(stripped_line)
        line = stripped_line.lstrip("-*• ").rstrip(":;")
        is_item = (
            not heading
            and 2 <= len(line) <= LIST_MAX_LINE_CHARS
            and not line.endswith((".", "!", "?"))
        )
        if is_item:
            current.append(line)
            continue
        # The run that just ended belongs to the heading it was collected under.
        if len(current) >= LIST_MIN_RUN and (heading_ok or whole_page_ok):
            runs.append(current)
        current = []
        if heading:
            heading_ok = bool(_TOPIC_HEADING.search(heading.group(1)))
    if not runs:
        return None
    items = max(runs, key=len)[:LIST_MAX_ITEMS]
    sentence = f"{title} covers topics including: {', '.join(items)}."
    while len(sentence) > LIST_SENTENCE_MAX_CHARS and len(items) > LIST_MIN_RUN:
        items = items[:-1]
        sentence = f"{title} covers topics including: {', '.join(items)}."
    return sentence


class MediaWikiSource(Source):
    host = "en.wikipedia.org"
    name = "Wikipedia"
    trust = 1.0
    result_limit = 3
    intro_only = True       # full body is fetched instead for list questions
    harvest_lists = True

    def search(self, query):
        want_lists = query.qtype == "list"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.search_terms,
            "gsrlimit": self.result_limit,
            "prop": "extracts",
            "explaintext": 1,
            "exlimit": "max",
            "redirects": 1,
            "format": "json",
        }
        if self.intro_only and not want_lists:
            params["exintro"] = 1
        data = self.get(f"https://{self.host}/w/api.php", params)
        pages = data.get("query", {}).get("pages", {})
        passages = []
        # gsr "index" preserves search relevance order
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            raw = page.get("extract") or ""
            title = page.get("title", "")
            text = self.clean(raw)
            if self.harvest_lists and (want_lists or not self.intro_only):
                synthetic = harvest_list(raw, title)
                if synthetic:
                    # Prepended: survives truncation and gets the lead boost.
                    text = f"{synthetic} {text}"
            if len(text) < 40:
                continue
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
        # Drop "== Heading ==" lines so they can't get glued into sentences.
        text = re.sub(r"^\s*=+.*?=+\s*$", " ", text, flags=re.M)
        return re.sub(r"\s+", " ", text).strip()


class WikipediaSource(MediaWikiSource):
    pass


class WikiversitySource(MediaWikiSource):
    host = "en.wikiversity.org"
    name = "Wikiversity"
    trust = 0.95
    result_limit = 3
    intro_only = False       # course pages keep their lesson lists in the body


class WiktionarySource(MediaWikiSource):
    host = "en.wiktionary.org"
    name = "Wiktionary"
    trust = 0.85
    result_limit = 1
    intro_only = False  # Wiktionary entries have empty intros; content lives in sections
    harvest_lists = False

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
