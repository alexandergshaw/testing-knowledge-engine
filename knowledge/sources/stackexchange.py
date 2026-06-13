"""Stack Exchange adapter via the keyless API quota — works for any SE site
(Stack Overflow, CS Educators, Software Engineering, ...)."""

import re
from html import unescape

from .base import Passage, Source, strip_html

API = "https://api.stackexchange.com/2.3"
MAX_ANSWER_CHARS = 2000
QUESTION_LIMIT = 2
MAX_CODE_BLOCKS = 3

_PRE_BLOCK = re.compile(r"<pre[^>]*>(.*?)</pre>", re.S)
_TAGS = re.compile(r"<[^>]+>")


def extract_code_blocks(body):
    """Verbatim code from an answer's <pre> blocks — these are dropped from the
    prose text by strip_html, but they're exactly what makes a worked example."""
    blocks = []
    for match in _PRE_BLOCK.findall(body):
        code = unescape(_TAGS.sub("", match)).strip("\n")
        if code.strip():
            blocks.append(code)
        if len(blocks) >= MAX_CODE_BLOCKS:
            break
    return blocks


class StackExchangeSource(Source):
    def __init__(self, site, name, trust):
        self.site = site
        self.name = name
        self.trust = trust

    def search(self, query):
        search = self.get(
            f"{API}/search/advanced",
            {
                "order": "desc",
                "sort": "relevance",
                "q": query.search_terms,
                "site": self.site,
                "answers": 1,
                "pagesize": QUESTION_LIMIT,
            },
        )
        questions = {item["question_id"]: item for item in search.get("items", [])}
        if not questions:
            return []

        ids = ";".join(str(question_id) for question_id in questions)
        answers = self.get(
            f"{API}/questions/{ids}/answers",
            {
                "site": self.site,
                "filter": "withbody",
                "order": "desc",
                "sort": "votes",
                "pagesize": 10,
            },
        )
        # Answers arrive votes-desc: the first one seen per question is its best.
        best = {}
        for answer in answers.get("items", []):
            best.setdefault(answer["question_id"], answer)

        passages = []
        for question_id, answer in best.items():
            question = questions[question_id]
            body = answer.get("body", "")
            text = strip_html(body)
            if len(text) < 40:
                continue
            passages.append(
                Passage(
                    text=text[:MAX_ANSWER_CHARS],
                    title=strip_html(question.get("title", "")),
                    url=question.get("link", ""),
                    source=self.name,
                    trust=self.trust,
                    code=extract_code_blocks(body),
                )
            )
        return passages
