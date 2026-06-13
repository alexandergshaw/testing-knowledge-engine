"""Shared python-pptx slide builders, used by both the project-materials
lectures (materials.py) and the objectives-driven module lectures
(lecture.py). Pure layout helpers — no content logic."""

import io

from pptx import Presentation
from pptx.util import Inches, Pt


def new_deck():
    return Presentation()


def add_title_slide(deck, title, subtitle=""):
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    slide.shapes.title.text = title
    if subtitle:
        slide.placeholders[1].text = subtitle
    return slide


def add_bullet_slide(deck, heading, bullets, sub_bullets=None):
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = heading
    body = slide.placeholders[1].text_frame
    body.clear()
    for index, bullet in enumerate(bullets):
        paragraph = body.paragraphs[0] if index == 0 else body.add_paragraph()
        paragraph.text = bullet
        paragraph.font.size = Pt(20)
    for sub in sub_bullets or []:
        paragraph = body.add_paragraph()
        paragraph.text = sub
        paragraph.level = 1
        paragraph.font.size = Pt(16)
    return slide


def add_content_slide(deck, title):
    """Title-only layout for slides we populate with custom text/code boxes."""
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = title
    return slide


def add_text_box(slide, text, top=1.4, height=1.9, size=18):
    box = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(8.6), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.text = text
    frame.paragraphs[0].font.size = Pt(size)
    return box


def add_code_box(slide, lines, top=3.4, height=3.4):
    box = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(8.6), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.name = "Consolas"
        paragraph.font.size = Pt(14)
    return box


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def deck_bytes(deck):
    output = io.BytesIO()
    deck.save(output)
    return output.getvalue()
