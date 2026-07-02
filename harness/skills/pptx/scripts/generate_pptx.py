#!/usr/bin/env python3
"""Generate a PowerPoint (.pptx) from a JSON slide description.

Standalone CLI adapted from the ``generate-pptx-api`` reference
(``scallighan/generate-pptx-api`` -> ``backend/server.py::generate_pptx_v2``).
It analyzes the placeholder layout of a template, computes a "weight" for each
layout and for each requested slide, and pairs every slide with the best-fitting
layout before populating its placeholders (title, subtitles, body text, object
content, pictures, tables) and any extra text boxes.

Usage:
    python generate_pptx.py --input slides.json --output deck.pptx [--template template.pptx]
    cat slides.json | python generate_pptx.py --output deck.pptx

Input JSON (either a list of slides, or an object with a "slides" list and an
optional "template" path):

    {
      "template": "template.pptx",            # optional; omit to use the built-in default
      "slides": [
        {
          "title": "Quarterly Review",
          "subtitles": ["FY25 Q3"],
          "text": ["Revenue up 12% YoY"],     # BODY placeholders
          "content": ["Additional talking point"],  # OBJECT placeholders
          "pictures": ["https://example.com/chart.png"],
          "tables": [
            {"headers": ["Year", "Revenue"], "rows": [["2024", "1M"], ["2025", "1.2M"]]}
          ],
          "extra_shapes": [
            {"shape_type": "text_box", "x": 914400, "y": 914400,
             "width": 3657600, "height": 914400, "text": "Draft"}
          ]
        }
      ]
    }

Every field is optional. Coordinates in ``extra_shapes`` are English Metric Units
(EMU); 914400 EMU == 1 inch. Pictures may be local paths or http(s) URLs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu

# Weights mirror the reference so slide content and layouts are scored on the
# same scale; rarer/heavier placeholder types dominate the match.
_WEIGHTS = {
    "title": 1,
    "subtitles": 2,
    "text": 5,
    "content": 10,
    "pictures": 100,
    "tables": 1000,
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


class SlideContent:
    """Requested content for a single slide, with a computed weight."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.title: str | None = data.get("title")
        self.subtitles: list[str] = list(data.get("subtitles", []) or [])
        self.text: list[str] = list(data.get("text", []) or [])
        self.content: list[str] = list(data.get("content", []) or [])
        self.pictures: list[str] = list(data.get("pictures", []) or [])
        self.tables: list[dict[str, Any]] = list(data.get("tables", []) or [])
        self.extra_shapes: list[dict[str, Any]] = list(data.get("extra_shapes", []) or [])
        self.weight = (
            (_WEIGHTS["title"] if self.title else 0)
            + len(self.subtitles) * _WEIGHTS["subtitles"]
            + len(self.text) * _WEIGHTS["text"]
            + len(self.content) * _WEIGHTS["content"]
            + len(self.pictures) * _WEIGHTS["pictures"]
            + len(self.tables) * _WEIGHTS["tables"]
        )


class SlideLayoutTemplate:
    """A template layout's placeholder profile and computed weight."""

    def __init__(self, layout_name: str, counts: dict[str, int]) -> None:
        self.layout_name = layout_name
        self.weight = (
            counts.get("title", 0) * _WEIGHTS["title"]
            + counts.get("subtitles", 0) * _WEIGHTS["subtitles"]
            + counts.get("text", 0) * _WEIGHTS["text"]
            + counts.get("content", 0) * _WEIGHTS["content"]
            + counts.get("pictures", 0) * _WEIGHTS["pictures"]
            + counts.get("tables", 0) * _WEIGHTS["tables"]
        )


def slide_analysis(prs: Presentation) -> dict[str, SlideLayoutTemplate]:
    """Return a ``lowercased-layout-name -> SlideLayoutTemplate`` mapping."""
    layout_templates: dict[str, SlideLayoutTemplate] = {}
    for layout in prs.slide_layouts:
        counts = {k: 0 for k in _WEIGHTS}
        for placeholder in layout.placeholders:
            ptype = placeholder.placeholder_format.type
            if ptype in (PP_PLACEHOLDER_TYPE.TITLE, PP_PLACEHOLDER_TYPE.CENTER_TITLE):
                counts["title"] += 1
            elif ptype == PP_PLACEHOLDER_TYPE.BODY:
                counts["text"] += 1
            elif ptype == PP_PLACEHOLDER_TYPE.SUBTITLE:
                counts["subtitles"] += 1
            elif ptype == PP_PLACEHOLDER_TYPE.OBJECT:
                counts["content"] += 1
            elif ptype == PP_PLACEHOLDER_TYPE.PICTURE:
                counts["pictures"] += 1
            elif ptype == PP_PLACEHOLDER_TYPE.TABLE:
                counts["tables"] += 1
        layout_templates[layout.name.lower()] = SlideLayoutTemplate(layout.name, counts)
    return layout_templates


def _append_notes(slide, notes_text: str) -> None:
    slide.notes_slide.notes_text_frame.text += notes_text


def _download_image(url: str) -> str:
    """Fetch a local-or-remote image to a temp file and return its path."""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return url  # treat as a local filesystem path
    ext_match = re.search(r"\.(jpg|jpeg|png|gif|bmp|tiff)", url, re.IGNORECASE)
    ext = ext_match.group(1) if ext_match else "jpg"
    fd, img_path = tempfile.mkstemp(suffix=f".{ext}")
    os.close(fd)
    _log(f"Downloading image from URL: {url}")
    with urllib.request.urlopen(url, timeout=30) as resp, open(img_path, "wb") as fh:  # noqa: S310
        fh.write(resp.read())
    return img_path


def _populate_slide(slide, sc: SlideContent) -> None:
    subtitles_i = text_i = content_i = pictures_i = tables_i = 0

    for placeholder in list(slide.placeholders):
        ptype = placeholder.placeholder_format.type
        if ptype in (PP_PLACEHOLDER_TYPE.TITLE, PP_PLACEHOLDER_TYPE.CENTER_TITLE) and sc.title:
            placeholder.text = sc.title
        elif ptype == PP_PLACEHOLDER_TYPE.SUBTITLE and subtitles_i < len(sc.subtitles):
            placeholder.text = sc.subtitles[subtitles_i]
            subtitles_i += 1
        elif ptype == PP_PLACEHOLDER_TYPE.BODY and text_i < len(sc.text):
            placeholder.text_frame.text = sc.text[text_i]
            text_i += 1
        elif ptype == PP_PLACEHOLDER_TYPE.OBJECT and content_i < len(sc.content):
            try:
                placeholder.text_frame.text = sc.content[content_i]
                content_i += 1
            except Exception as e:  # noqa: BLE001
                _log(f"Error inserting content into OBJECT placeholder: {e}")
                _append_notes(slide, f"Warning: could not insert content into OBJECT placeholder\n")
        elif ptype == PP_PLACEHOLDER_TYPE.PICTURE and pictures_i < len(sc.pictures):
            url = sc.pictures[pictures_i]
            pictures_i += 1
            try:
                placeholder.insert_picture(_download_image(url))
                _log(f"Inserted picture from {url}")
            except Exception as e:  # noqa: BLE001
                _log(f"Error downloading or inserting image: {e}")
                _append_notes(slide, f"Warning: could not download or insert image from {url}\n")
        elif ptype == PP_PLACEHOLDER_TYPE.TABLE and tables_i < len(sc.tables):
            try:
                table_data = sc.tables[tables_i]
                tables_i += 1
                headers = table_data.get("headers", [])
                data_rows = table_data.get("rows", [])
                if headers:
                    table = placeholder.insert_table(len(data_rows) + 1, len(headers)).table
                    for col, header in enumerate(headers):
                        table.cell(0, col).text = str(header)
                    for r, row_data in enumerate(data_rows, start=1):
                        for col, cell in enumerate(row_data):
                            table.cell(r, col).text = str(cell)
                    _log("Inserted table into slide.")
            except Exception as e:  # noqa: BLE001
                _log(f"Error inserting table: {e}")

    for es in sc.extra_shapes:
        try:
            if str(es.get("shape_type", "")).lower() in ("text_box", "textbox"):
                shape = slide.shapes.add_textbox(
                    Emu(int(es["x"])), Emu(int(es["y"])),
                    Emu(int(es["width"])), Emu(int(es["height"])),
                )
                if es.get("text") and shape.has_text_frame:
                    shape.text = es["text"]
                    _log(f"Added extra text box with text: {es['text']}")
        except Exception as e:  # noqa: BLE001
            _log(f"Error adding extra shape {es}: {e}")

    for shape in slide.shapes:
        if shape.has_text_frame and shape.text:
            shape.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    # Surface any content that had no matching placeholder as slide notes.
    leftovers = {
        "subtitles": (subtitles_i, sc.subtitles),
        "text": (text_i, sc.text),
        "content": (content_i, sc.content),
        "pictures": (pictures_i, sc.pictures),
        "tables": (tables_i, sc.tables),
    }
    for label, (used, items) in leftovers.items():
        if used < len(items):
            _append_notes(slide, f"Warning: not all {label} were used for this slide.\n")


def _best_layout(sc: SlideContent, layouts: dict[str, SlideLayoutTemplate]) -> SlideLayoutTemplate | None:
    """Exact match by title, else the layout with the closest weight."""
    if sc.title and sc.title.lower() in layouts:
        return layouts[sc.title.lower()]
    best: SlideLayoutTemplate | None = None
    smallest_diff = float("inf")
    for layout in layouts.values():
        diff = abs(sc.weight - layout.weight)
        if diff <= smallest_diff:
            smallest_diff = diff
            best = layout
    return best


def generate_pptx(data: dict[str, Any], output_path: str) -> str:
    template = data.get("template")
    prs = Presentation(template) if template else Presentation()

    layouts = slide_analysis(prs)
    _log(f"Analyzed {len(layouts)} layouts: {sorted(layouts)}")

    for raw in data.get("slides", []):
        sc = SlideContent(raw)
        best = _best_layout(sc, layouts)
        if best is None:
            _log(f"No matching layout for slide (weight={sc.weight}); skipping.")
            continue
        _log(f"Matched layout '{best.layout_name}' (weight={best.weight}) for slide weight={sc.weight}")
        slide = prs.slides.add_slide(prs.slide_layouts.get_by_name(best.layout_name))
        _populate_slide(slide, sc)

    prs.save(output_path)
    return output_path


def _load_input(path: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if path in (None, "-") else open(path, encoding="utf-8").read()
    body = json.loads(raw)
    if isinstance(body, list):
        body = {"slides": body}
    if not isinstance(body, dict):
        raise ValueError("Input JSON must be a slide list or an object with a 'slides' key.")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a .pptx from a JSON slide description.")
    parser.add_argument("--input", "-i", default="-", help="Input JSON file, or '-' for stdin (default).")
    parser.add_argument("--output", "-o", default=None, help="Output .pptx path (default: generated_presentation_<ts>.pptx).")
    parser.add_argument("--template", "-t", default=None, help="Template .pptx (overrides any 'template' in the JSON).")
    args = parser.parse_args()

    data = _load_input(args.input)
    if args.template:
        data["template"] = args.template
    output_path = args.output or f"generated_presentation_{int(time.time())}.pptx"

    saved = generate_pptx(data, output_path)
    print(saved)  # stdout: the path, for easy capture by callers
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
