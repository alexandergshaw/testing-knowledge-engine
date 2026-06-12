"""Stack Overflow adapter via the Stack Exchange API (keyless quota)."""

from .base import Passage, Source, strip_html

API = "https://api.stackexchange.com/2.3"
MAX_ANSWER_CHARS = 2000


class StackOverflowSource(Source):
    name = "Stack Overflow"
    trust = 0.9
    site = "stackoverflow"

    def search(self, query):
        search = self.get(
            f"{API}/search/advanced",
            {
                "order": "desc",
                "sort": "relevance",
                "q": query.topic,
                "site": self.site,
                "accepted": "True",
                "pagesize": 2,
            },
        )
        questions = {
            item["accepted_answer_id"]: item
            for item in search.get("items", [])
            if item.get("accepted_answer_id")
        }
        if not questions:
            return []

        ids = ";".join(str(answer_id) for answer_id in questions)
        answers = self.get(
            f"{API}/answers/{ids}",
            {"site": self.site, "filter": "withbody", "order": "desc", "sort": "votes"},
        )
        passages = []
        for answer in answers.get("items", []):
            question = questions.get(answer.get("answer_id"))
            if question is None:
                continue
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
