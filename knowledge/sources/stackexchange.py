"""Stack Exchange adapter via the keyless API quota — works for any SE site
(Stack Overflow, CS Educators, Software Engineering, ...)."""

from .base import Passage, Source, strip_html

API = "https://api.stackexchange.com/2.3"
MAX_ANSWER_CHARS = 2000
QUESTION_LIMIT = 2


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
            text = strip_html(answer.get("body", ""))
            if len(text) < 40:
                continue
            passages.append(
                Passage(
                    text=text[:MAX_ANSWER_CHARS],
                    title=strip_html(question.get("title", "")),
                    url=question.get("link", ""),
                    source=self.name,
                    trust=self.trust,
                )
            )
        return passages
