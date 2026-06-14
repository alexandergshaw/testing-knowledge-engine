"""Shared python-pptx slide builders plus a professional theme, used by both
the project-materials lectures (materials.py) and the objectives-driven module
lectures (lecture.py).

House style for every returned deck:
- 16:9, a consistent professional theme (fonts, accent color, footer).
- Title-Cased, self-contained slide titles.
- At most TWO self-contained bullets per content slide; any overflow is moved
  into the slide's speaker notes so nothing is lost.
- Agenda/reference enumerations use a compact non-bullet list slide instead.
"""

import io
import re

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

MAX_BULLETS = 2
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


class Theme:
    title_font = "Calibri"
    body_font = "Calibri"
    mono_font = "Consolas"
    accent = RGBColor(0x2F, 0x5B, 0x9E)        # professional blue
    title_color = RGBColor(0x1A, 0x2A, 0x44)
    body_color = RGBColor(0x23, 0x2A, 0x35)
    muted_color = RGBColor(0x8A, 0x90, 0x9C)
    background = RGBColor(0xFF, 0xFF, 0xFF)


THEME = Theme()

_SMALL_WORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "of", "to", "in", "on", "at",
    "for", "with", "by", "as", "is", "are", "vs", "via", "per",
}


# --- text normalization ------------------------------------------------------


def clean_title(text):
    """Trim, drop trailing punctuation, and Title-Case a heading while keeping
    acronyms / mixed-case tokens (Python, I/O, HTML) intact."""
    text = re.sub(r"\s+", " ", str(text)).strip().rstrip(".,;:!")
    words = text.split(" ")
    out = []
    for index, word in enumerate(words):
        edge = index == 0 or index == len(words) - 1
        if not word:
            continue
        if (len(word) > 1 and any(c.isupper() for c in word[1:])) or (word.isupper() and len(word) > 1):
            out.append(word)  # preserve Python, I/O, HTML, acronyms
        elif not edge and word.lower() in _SMALL_WORDS:
            out.append(word.lower())
        else:
            out.append(word[:1].upper() + word[1:].lower())
    return " ".join(out)[:90]


def clean_bullet(text):
    """Make a bullet stand on its own: strip leading list/citation markers,
    capitalize, and ensure terminal punctuation."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"^(?:[-*•–]|\d+[.)])\s*", "", text)  # leading markers
    text = re.sub(r"\s*\[\d+\]", "", text)              # [n] citation markers
    text = text.strip()
    if not text:
        return ""
    text = text[:1].upper() + text[1:]
    if text[-1] not in ".!?:":
        text += "."
    return text


# --- theme application -------------------------------------------------------


def _apply_background(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = THEME.background


def _accent_bar(slide):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, Inches(0.16))
    bar.fill.solid()
    bar.fill.fore_color.rgb = THEME.accent
    bar.line.fill.background()
    bar.shadow.inherit = False


def _style_title(slide, size=30):
    title = slide.shapes.title
    if title is None:
        return
    for paragraph in title.text_frame.paragraphs:
        paragraph.font.name = THEME.title_font
        paragraph.font.size = Pt(size)
        paragraph.font.bold = True
        paragraph.font.color.rgb = THEME.title_color
        for run in paragraph.runs:
            run.font.name = THEME.title_font
            run.font.size = Pt(size)
            run.font.bold = True
            run.font.color.rgb = THEME.title_color


def _add_footer(deck, slide, footer):
    number = len(deck.slides)
    text = f"{footer}  ·  {number}" if footer else str(number)
    box = slide.shapes.add_textbox(Inches(0.4), Inches(7.05), Inches(12.5), Inches(0.35))
    paragraph = box.text_frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.size = Pt(10)
    paragraph.font.name = THEME.body_font
    paragraph.font.color.rgb = THEME.muted_color


def _decorate(deck, slide, footer):
    _apply_background(slide)
    _accent_bar(slide)
    _style_title(slide)
    _add_footer(deck, slide, footer)


def _style_body_paragraph(paragraph, size, font=None, color=None):
    paragraph.font.name = font or THEME.body_font
    paragraph.font.size = Pt(size)
    paragraph.font.color.rgb = color or THEME.body_color


# --- slide builders ----------------------------------------------------------


def new_deck():
    deck = Presentation()
    deck.slide_width = SLIDE_WIDTH
    deck.slide_height = SLIDE_HEIGHT
    return deck


def add_title_slide(deck, title, subtitle=""):
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    slide.shapes.title.text = clean_title(title)
    if subtitle:
        slide.placeholders[1].text = subtitle
        for paragraph in slide.placeholders[1].text_frame.paragraphs:
            _style_body_paragraph(paragraph, 20, color=THEME.muted_color)
    _apply_background(slide)
    _accent_bar(slide)
    _style_title(slide, size=40)
    return slide


def add_bullet_slide(deck, heading, bullets, notes="", footer=None):
    """A content slide with at most two self-contained bullets. Bullets beyond
    two (and any extra `notes`) go to the slide's speaker notes."""
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = clean_title(heading)

    cleaned = [b for b in (clean_bullet(item) for item in bullets) if b]
    shown = cleaned[:MAX_BULLETS]
    body = slide.placeholders[1].text_frame
    body.clear()
    for index, bullet in enumerate(shown):
        paragraph = body.paragraphs[0] if index == 0 else body.add_paragraph()
        paragraph.text = bullet
        _style_body_paragraph(paragraph, 24)

    note_parts = []
    overflow = cleaned[MAX_BULLETS:]
    if overflow:
        note_parts.append("Also covers:\n" + "\n".join(f"- {b}" for b in overflow))
    if notes:
        note_parts.append(notes)
    if note_parts:
        set_notes(slide, "\n\n".join(note_parts))

    _decorate(deck, slide, footer)
    return slide


def add_list_slide(deck, heading, items, footer=None):
    """A compact, non-bullet list (small font) for agendas and references —
    reference material, exempt from the two-bullet rule."""
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = clean_title(heading)
    box = slide.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(12), Inches(5.3))
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = str(item)
        _style_body_paragraph(paragraph, 16)
    _decorate(deck, slide, footer)
    return slide


def add_content_slide(deck, title, footer=None):
    """Title-only slide we populate with custom text/code boxes (0 bullets)."""
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = clean_title(title)
    _decorate(deck, slide, footer)
    return slide


def add_text_box(slide, text, top=1.5, height=1.9, size=18):
    box = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(12), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.text = text
    _style_body_paragraph(frame.paragraphs[0], size)
    return box


def add_code_box(slide, lines, top=3.4, height=3.2):
    box = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(12), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        _style_body_paragraph(paragraph, 14, font=THEME.mono_font)
    return box


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def deck_bytes(deck):
    output = io.BytesIO()
    deck.save(output)
    return output.getvalue()
