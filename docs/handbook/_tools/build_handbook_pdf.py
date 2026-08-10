from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
HANDBOOK_DIR = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
DEPS_DIR = HANDBOOK_DIR / "_deps"
sys.path.insert(0, str(DEPS_DIR))

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreakIfNotEmpty,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


SOURCE = HANDBOOK_DIR / "Settlers_5_Blender_Plugin_Handbook_EN.md"
DEFAULT_OUTPUT = HANDBOOK_DIR / "Settlers_5_Blender_Plugin_Handbook_EN.pdf"
DOCUMENT_TITLE = "The Settlers 5 - Novator12 DFF - Tool Handbook"
DOCUMENT_AUTHOR = "Novator12 DFF Plugin documentation"
DOCUMENT_SUBJECT = (
    "Handbook for The Settlers 5 model and animation workflows with "
    "Novator12 DFF Plugin Blender v5 3.2.1 in Blender 5.0.1"
)
RUNNING_HEADER = "Novator12 DFF Tool Handbook"
TOC_MARKER = "<!-- PDF_TOC -->"
PAGE_WIDTH, PAGE_HEIGHT = LETTER
MARGIN = inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
CONTENT_HEIGHT = PAGE_HEIGHT - 2 * MARGIN


def register_fonts() -> tuple[str, str, str, str]:
    candidates = [
        (
            Path(r"C:\Windows\Fonts\calibri.ttf"),
            Path(r"C:\Windows\Fonts\calibrib.ttf"),
            Path(r"C:\Windows\Fonts\calibrii.ttf"),
            Path(r"C:\Windows\Fonts\calibriz.ttf"),
        ),
        (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\ariali.ttf"),
            Path(r"C:\Windows\Fonts\arialbi.ttf"),
        ),
    ]
    for regular, bold, italic, bold_italic in candidates:
        if all(path.exists() for path in (regular, bold, italic, bold_italic)):
            pdfmetrics.registerFont(TTFont("Handbook", str(regular)))
            pdfmetrics.registerFont(TTFont("Handbook-Bold", str(bold)))
            pdfmetrics.registerFont(TTFont("Handbook-Italic", str(italic)))
            pdfmetrics.registerFont(TTFont("Handbook-BoldItalic", str(bold_italic)))
            pdfmetrics.registerFontFamily(
                "Handbook",
                normal="Handbook",
                bold="Handbook-Bold",
                italic="Handbook-Italic",
                boldItalic="Handbook-BoldItalic",
            )
            return "Handbook", "Handbook-Bold", "Handbook-Italic", "Handbook-BoldItalic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"


FONT, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC = register_fonts()


def normalize_text(value: str) -> str:
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def inline_markup(value: str) -> str:
    value = normalize_text(value.strip())
    placeholders: dict[str, str] = {}

    def hold(fragment: str) -> str:
        key = f"@@H{len(placeholders)}@@"
        placeholders[key] = fragment
        return key

    def code_repl(match: re.Match[str]) -> str:
        return hold(f'<font name="Courier">{html.escape(match.group(1))}</font>')

    value = re.sub(r"`([^`]+)`", code_repl, value)
    value = html.escape(value, quote=False)

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def link_repl(match: re.Match[str]) -> str:
        label = html.unescape(match.group(1))
        target = html.unescape(match.group(2))
        if target.startswith(("https://", "http://")):
            return hold(
                '<a href="{}" color="#2E74B5"><u>{}</u></a>'.format(
                    html.escape(target, quote=True),
                    html.escape(label),
                )
            )
        # Local Markdown targets are useful in the source handbook but are not
        # portable once the PDF is moved. Render their labels cleanly instead
        # of exposing raw ``[label](path)`` syntax in prose and tables.
        return hold(label)

    value = link_pattern.sub(link_repl, value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    value = value.replace("  ", " ")
    # Resolve outer placeholders before inner placeholders. This preserves
    # inline code used inside a Markdown link label.
    for key in reversed(list(placeholders)):
        fragment = placeholders[key]
        value = value.replace(key, fragment)
    return value


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="HandbookBody",
        parent=styles["BodyText"],
        fontName=FONT,
        fontSize=9.5,
        leading=12.0,
        textColor=colors.HexColor("#1F2933"),
        spaceAfter=6,
        allowWidows=0,
        allowOrphans=0,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookTitle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=28,
        leading=32,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#163A5F"),
        spaceAfter=18,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookH1",
        parent=styles["Heading1"],
        fontName=FONT_BOLD,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#2E74B5"),
        spaceBefore=0,
        spaceAfter=10,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookH2",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1F4D78"),
        spaceBefore=10,
        spaceAfter=7,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookH3",
        parent=styles["Heading3"],
        fontName=FONT_BOLD,
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#274C68"),
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookList",
        parent=styles["HandbookBody"],
        leftIndent=18,
        firstLineIndent=-10,
        bulletIndent=7,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookCaption",
        parent=styles["HandbookBody"],
        fontName=FONT_ITALIC,
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#52606D"),
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=9,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookSmall",
        parent=styles["HandbookBody"],
        fontSize=7.5,
        leading=9.2,
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookTOCLevel0",
        parent=styles["HandbookBody"],
        fontName=FONT_BOLD,
        fontSize=10,
        leading=14,
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=4,
        spaceAfter=2,
        textColor=colors.HexColor("#163A5F"),
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookTOCLevel1",
        parent=styles["HandbookSmall"],
        fontName=FONT,
        fontSize=8.5,
        leading=11,
        leftIndent=18,
        firstLineIndent=0,
        spaceBefore=1,
        spaceAfter=1,
        textColor=colors.HexColor("#334E68"),
    )
)
styles.add(
    ParagraphStyle(
        name="HandbookCoverMeta",
        parent=styles["HandbookBody"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334E68"),
        spaceAfter=5,
    )
)


class HandbookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=LETTER,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title=DOCUMENT_TITLE,
            author=DOCUMENT_AUTHOR,
            subject=DOCUMENT_SUBJECT,
        )
        frame = Frame(MARGIN, MARGIN, CONTENT_WIDTH, CONTENT_HEIGHT, id="content")
        self.addPageTemplates(
            [
                PageTemplate(id="Cover", frames=[frame], onPage=self.draw_cover_page),
                PageTemplate(id="Body", frames=[frame], onPage=self.draw_body_page),
            ]
        )
        self._outline_counter = 0

    def beforeDocument(self):
        # multiBuild performs at least two passes so the TableOfContents can
        # resolve page numbers. Bookmark names must remain stable per pass.
        self._outline_counter = 0

    @staticmethod
    def draw_cover_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#163A5F"))
        canvas.rect(0, PAGE_HEIGHT - 0.23 * inch, PAGE_WIDTH, 0.23 * inch, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#2E74B5"))
        canvas.rect(0, 0, PAGE_WIDTH, 0.12 * inch, fill=1, stroke=0)
        canvas.restoreState()

    @staticmethod
    def draw_body_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_HEIGHT - 0.62 * inch, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 0.62 * inch)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#52606D"))
        canvas.drawString(MARGIN, PAGE_HEIGHT - 0.5 * inch, RUNNING_HEADER)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        level = getattr(flowable, "_outline_level", None)
        if level is None:
            return
        key = f"heading-{self._outline_counter}"
        self._outline_counter += 1
        title = normalize_text(flowable.getPlainText())
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=level > 0)
        toc_level = getattr(flowable, "_toc_level", None)
        if toc_level is not None:
            self.notify("TOCEntry", (toc_level, title, self.page, key))


def heading(text: str, level: int) -> Paragraph:
    style_name = {1: "HandbookH1", 2: "HandbookH2", 3: "HandbookH3"}[min(level, 3)]
    paragraph = Paragraph(inline_markup(text), styles[style_name])
    # The cover subtitle is an H2 in Markdown for visual hierarchy, but it has
    # no preceding chapter outline node and must not enter the PDF outline.
    if not text.startswith(("User Handbook for", "Blender 5.0.1 Guide")):
        paragraph._outline_level = min(level - 1, 2)
        # Keep the printed contents useful and compact: H1 Part/chapter
        # entries plus numbered H2 sections. H3 details remain available in
        # the PDF outline without expanding the TOC by several pages.
        if text != "Contents" and level <= 2:
            paragraph._toc_level = level - 1
    return paragraph


def table_of_contents() -> TableOfContents:
    toc = TableOfContents()
    toc.levelStyles = [styles["HandbookTOCLevel0"], styles["HandbookTOCLevel1"]]
    toc.dotsMinLevel = 0
    return toc


def image_flowable(relative_path: str, alt_text: str):
    image_path = (HANDBOOK_DIR / relative_path).resolve()
    if not image_path.exists():
        return Paragraph(
            f'<font color="#B42318"><b>Missing image:</b> {html.escape(relative_path)}</font>',
            styles["HandbookBody"],
        )
    with PILImage.open(image_path) as bitmap:
        pixel_width, pixel_height = bitmap.size
    max_width = CONTENT_WIDTH
    max_height = 4.85 * inch
    ratio = min(max_width / pixel_width, max_height / pixel_height)
    rendered = Image(str(image_path), width=pixel_width * ratio, height=pixel_height * ratio)
    rendered.hAlign = "CENTER"
    rendered._alt_text = alt_text
    return rendered


def parse_table(lines: list[str]) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) > 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        rows.pop(1)
    columns = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (columns - len(row)))
    font_size = 7.2 if columns >= 5 else 8.0
    cell_style = ParagraphStyle(
        "DynamicTableCell",
        parent=styles["HandbookSmall"],
        fontSize=font_size,
        leading=font_size + 1.5,
        spaceAfter=0,
    )
    data = [[Paragraph(inline_markup(cell), cell_style) for cell in row] for row in rows]
    # Give the first column a little more space in reference tables.
    if columns == 2:
        widths = [CONTENT_WIDTH * 0.34, CONTENT_WIDTH * 0.66]
    elif columns == 3:
        widths = [CONTENT_WIDTH * 0.23, CONTENT_WIDTH * 0.31, CONTENT_WIDTH * 0.46]
    elif columns == 4:
        widths = [CONTENT_WIDTH * 0.20, CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.30]
    else:
        widths = [CONTENT_WIDTH / columns] * columns
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    # Use native flowable spacing so a table that exactly fills a page does
    # not push a standalone Spacer onto the next page before a chapter break.
    table.spaceAfter = 7
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163A5F")),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BCCCDC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def markdown_to_story(markdown_text: str):
    lines = markdown_text.replace("\r\n", "\n").split("\n")
    story = []
    paragraph_lines: list[str] = []
    first_h1 = True
    in_code = False
    code_lines: list[str] = []
    previous_was_image = False
    previous_was_heading = False

    def flush_paragraph():
        nonlocal paragraph_lines, previous_was_image, previous_was_heading
        if not paragraph_lines:
            return
        value = " ".join(part.strip() for part in paragraph_lines if part.strip()).strip()
        paragraph_lines = []
        if not value:
            return
        if value.startswith("*Figure ") and value.endswith("*"):
            story.append(Paragraph(inline_markup(value[1:-1]), styles["HandbookCaption"]))
        else:
            story.append(Paragraph(inline_markup(value), styles["HandbookBody"]))
        previous_was_image = False
        previous_was_heading = False

    index = 0
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                code_text = normalize_text("\n".join(code_lines))
                story.append(
                    Preformatted(
                        code_text,
                        ParagraphStyle(
                            "HandbookCode",
                            fontName="Courier",
                            fontSize=7.2,
                            leading=9.0,
                            leftIndent=8,
                            rightIndent=8,
                            backColor=colors.HexColor("#F5F7FA"),
                            borderColor=colors.HexColor("#D9E2EC"),
                            borderWidth=0.5,
                            borderPadding=6,
                            spaceBefore=4,
                            spaceAfter=8,
                        ),
                        maxLineLength=92,
                    )
                )
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue

        if stripped == TOC_MARKER:
            flush_paragraph()
            story.append(table_of_contents())
            previous_was_image = False
            previous_was_heading = False
            index += 1
            continue
        if in_code:
            code_lines.append(raw)
            index += 1
            continue

        # Keep figure captions as their own centered paragraphs even when the
        # Markdown author did not leave a blank line after the caption.
        if stripped.startswith("*Figure ") and stripped.endswith("*"):
            flush_paragraph()
            story.append(Paragraph(inline_markup(stripped[1:-1]), styles["HandbookCaption"]))
            previous_was_image = False
            previous_was_heading = False
            index += 1
            continue

        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_paragraph()
            alt_text, relative_path = image_match.groups()
            image = image_flowable(relative_path, alt_text)
            # A figure and the immediately following italic Figure caption are
            # one semantic unit.  Keeping them together prevents a full image
            # from ending a page while its caption is stranded on the next.
            caption_index = index + 1
            while caption_index < len(lines) and not lines[caption_index].strip():
                caption_index += 1
            caption_text = lines[caption_index].strip() if caption_index < len(lines) else ""
            caption_is_figure = caption_text.startswith("*Figure ") and caption_text.endswith("*")
            if not previous_was_heading:
                story.append(CondPageBreak(2.2 * inch))
            if caption_is_figure:
                caption = Paragraph(
                    inline_markup(caption_text[1:-1]),
                    styles["HandbookCaption"],
                )
                story.append(KeepTogether([image, caption]))
                index = caption_index
            else:
                story.append(image)
            previous_was_image = True
            previous_was_heading = False
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            level = min(len(heading_match.group(1)), 3)
            title = heading_match.group(2).strip()
            if level == 1:
                if first_h1:
                    story.append(Spacer(1, 0.85 * inch))
                    story.append(Paragraph(inline_markup(title), styles["HandbookTitle"]))
                    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2E74B5")))
                    story.append(Spacer(1, 0.25 * inch))
                    first_h1 = False
                    story.append(NextPageTemplate("Body"))
                else:
                    # A preceding flowable (for example a table) may have
                    # already filled the page exactly and triggered an
                    # automatic page advance. Avoid consuming that fresh page
                    # with a second, now-redundant chapter break.
                    story.append(PageBreakIfNotEmpty())
                    story.append(heading(title, level))
            else:
                story.append(CondPageBreak(0.85 * inch))
                story.append(heading(title, level))
            previous_was_image = False
            previous_was_heading = True
            index += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            flush_paragraph()
            table_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and "|" in candidate[1:]):
                    break
                table_lines.append(candidate)
                index += 1
            if table_lines:
                if not previous_was_heading:
                    story.append(CondPageBreak(1.1 * inch))
                story.append(parse_table(table_lines))
            previous_was_image = False
            previous_was_heading = False
            continue

        quote_match = re.match(r"^>\s?(.*)$", stripped)
        if quote_match:
            flush_paragraph()
            quote_parts = []
            while index < len(lines):
                match = re.match(r"^>\s?(.*)$", lines[index].strip())
                if not match:
                    break
                quote_parts.append(match.group(1))
                index += 1
            quote_text = " ".join(quote_parts)
            tone = colors.HexColor("#FFF4E5") if "WARNING" in quote_text.upper() else colors.HexColor("#EAF4FB")
            quote_table = Table(
                [[Paragraph(inline_markup(quote_text), styles["HandbookBody"])]],
                colWidths=[CONTENT_WIDTH],
            )
            quote_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), tone),
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#7B8794")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(quote_table)
            story.append(Spacer(1, 6))
            previous_was_image = False
            previous_was_heading = False
            continue

        list_match = re.match(r"^(\s*)([-+*]|\d+[.)])\s+(.+)$", raw)
        if list_match:
            flush_paragraph()
            indentation, marker, value = list_match.groups()
            indent_level = min(len(indentation) // 2, 3)
            bullet = "•" if not marker[0].isdigit() else marker.rstrip(".)") + "."
            list_style = ParagraphStyle(
                f"HandbookList{indent_level}",
                parent=styles["HandbookList"],
                leftIndent=18 + indent_level * 14,
                bulletIndent=7 + indent_level * 14,
            )
            story.append(Paragraph(inline_markup(value), list_style, bulletText=bullet))
            previous_was_image = False
            previous_was_heading = False
            index += 1
            continue

        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#BCCCDC")))
            story.append(Spacer(1, 6))
            previous_was_image = False
            previous_was_heading = False
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            if previous_was_image:
                story.append(Spacer(1, 4))
            index += 1
            continue

        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    if in_code and code_lines:
        story.append(Preformatted(normalize_text("\n".join(code_lines)), styles["Code"]))
    return story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if not SOURCE.exists():
        raise SystemExit(f"Missing handbook Markdown: {SOURCE}")
    markdown_text = SOURCE.read_text(encoding="utf-8")
    story = markdown_to_story(markdown_text)
    output.parent.mkdir(parents=True, exist_ok=True)
    story_item_count = len(story)
    document = HandbookDocTemplate(str(output))
    document.multiBuild(story)
    print(f"HANDBOOK_PDF={output}")
    print(f"HANDBOOK_STORY_ITEMS={story_item_count}")


if __name__ == "__main__":
    main()
