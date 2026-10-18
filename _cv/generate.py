#!/usr/bin/env python3
"""Generate every version of the CV from _cv/cv.yml. Run it through ./generate-cv.sh

Published (commit them):
  cv/index.html                               the CV page: the designed CV, and a preview of
                                              the Classic one in A4 and US Letter
  cv/cv-nicolas-bailliet.pdf                  designed CV, A4
  cv/cv-nicolas-bailliet-classic-a4.pdf       Classic CV (sober, one column), A4
  cv/cv-nicolas-bailliet-classic-letter.pdf   Classic CV, US Letter
  figures/og-cv.png                           the share image (loads its fonts from Google Fonts)

Every PDF must fit on one page. After generating, the outputs are checked: the summary
reads back word for word from each PDF, and words the site must not use are absent.

In cv.yml, `hide_in: [classic]` on an entry, a bullet, a skill, a section or an availability
detail leaves it out of both Classic versions; a version name targets one version only.
"""
import copy
import re
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOCAL = HERE / "local"  # git-ignored: intermediate files

VERSIONS = ("design-a4", "classic-a4", "classic-letter")
GROUPS = {"design": ("design-a4",), "classic": ("classic-a4", "classic-letter")}
PDFS = {
    "design-a4": ROOT / "cv" / "cv-nicolas-bailliet.pdf",
    "classic-a4": ROOT / "cv" / "cv-nicolas-bailliet-classic-a4.pdf",
    "classic-letter": ROOT / "cv" / "cv-nicolas-bailliet-classic-letter.pdf",
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Words the published site must not contain (the sober CV is called Classic, and the
# internship search is no longer limited to other countries).
FORBIDDEN = {"ATS": r"\bATS\b", "outside France": r"(?i)outside France", "abroad": r"(?i)\babroad\b",
             "third-year": r"(?i)third-year"}

# Screen-mode styles for the CV thumbnail of the share image.
OG_THUMBNAIL_STYLES = """
() => {
  for (const sel of ['.btn-container', '.btn-container-right']) document.querySelector(sel).style.display = 'none';
  document.documentElement.style.overflow = 'hidden';
  Object.assign(document.body.style, { padding: '0', margin: '0', overflow: 'hidden' });
  Object.assign(document.querySelector('.cv-container').style, { boxShadow: 'none', margin: '0', maxWidth: '210mm',
    height: '297mm', overflow: 'hidden', gridTemplateColumns: '175px 1fr' });
}
"""


# ── Content ──

def select(cv, version):
    """The content as one version sees it: list items whose `hide_in` names the version, or a
    group it belongs to, are dropped."""
    names = set(VERSIONS) | set(GROUPS)
    hidden_for = {version} | {group for group, members in GROUPS.items() if version in members}

    def walk(node, where):
        if isinstance(node, dict):
            return {key: walk(value, f"{where}.{key}") for key, value in node.items() if key != "hide_in"}
        if isinstance(node, list):
            kept = []
            for index, item in enumerate(node):
                hidden = item.get("hide_in", []) if isinstance(item, dict) else []
                unknown = set(hidden) - names
                if unknown:
                    sys.exit(f"cv.yml {where}[{index}]: hide_in names unknown version(s) {', '.join(sorted(unknown))}; "
                             f"use {', '.join(sorted(names))}")
                if hidden_for & set(hidden):
                    continue
                item = walk(item, f"{where}[{index}]")
                # An item written as {text, hide_in} is a plain string once hide_in is resolved.
                kept.append(item["text"] if isinstance(item, dict) and set(item) == {"text"} else item)
            return kept
        return node

    return walk(copy.deepcopy(cv), "cv")


# ── Template helpers ──

def inline(text):
    """Escape text, then turn **bold** into <strong>."""
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text))))


def plain(text):
    """Text without inline markup."""
    return text.replace("**", "")


def bare_url(url):
    """'https://github.com/baillietn' -> 'github.com/baillietn'."""
    return re.sub(r"^https?://", "", url)


def parse_date(value):
    """'2025-06' -> (2025, 6); 'present' -> None."""
    if value == "present":
        return None
    year, _, month = str(value).partition("-")
    return int(year), int(month) if month else None


def design_dates(start, end, expected=False):
    """Date range on the designed CV: months within one year ('Jun–Aug 2025'), years otherwise
    ('2023–Present', '2023–2027 (expected)')."""
    s, e = parse_date(start), parse_date(end)
    if e and s[0] == e[0] and s[1] and e[1]:
        text = f"{MONTHS[s[1] - 1]}–{MONTHS[e[1] - 1]} {s[0]}"
    else:
        text = f"{s[0]}–{e[0] if e else 'Present'}"
    return f"{text} (expected)" if expected else text


def classic_dates(start, end, expected=False):
    """Date range on the Classic CV, one format everywhere: 'Jun 2025 – Aug 2025',
    'Sep 2023 – Sep 2027 (expected)'."""
    def fmt(value):
        date = parse_date(value)
        if date is None:
            return "Present"
        return f"{MONTHS[date[1] - 1]} {date[0]}" if date[1] else str(date[0])

    text = f"{fmt(start)} – {fmt(end)}"
    return f"{text} (expected)" if expected else text


def keep_hyphenated_words_whole(html):
    """Wrap words like 'pre-training' so that no line breaks inside them.

    A word split after its hyphen at a line end is glued back without the hyphen
    by text extractors ('Cosmopedia-v2' -> 'Cosmopediav2'), which corrupts keywords.
    """
    parts = re.split(r"(<[^>]+>)", html)  # tags at odd indexes, text at even ones
    parts[::2] = [re.sub(r"(?<![\w-])(\w+(?:-\w+)+)(?![\w-])", r'<span class="nobreak">\1</span>', text)
                  for text in parts[::2]]
    return "".join(parts)


# ── Output ──

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def without_dates(pdf_bytes):
    return re.sub(rb"/(CreationDate|ModDate) \(D:[^)]*\)", b"", pdf_bytes)


def page_count(pdf_bytes):
    return len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))


# How far the content of the designed CV runs past the bottom of its fixed A4 page, in pixels.
DESIGN_OVERFLOW = """
() => {
  const pageBottom = document.querySelector('.cv-container').getBoundingClientRect().bottom;
  return Math.max(...[...document.querySelectorAll('.sidebar, .main-content')].map(column =>
    column.lastElementChild.getBoundingClientRect().bottom + parseFloat(getComputedStyle(column).paddingBottom) - pageBottom));
}
"""


def print_pdf(browser, html_path, pdf_path, fixed_page=False, fonts=()):
    """Print a page to a one-page PDF; paper size and margins come from the page's own CSS.

    `fonts` lists CSS font shorthands that must be loaded, so that a font that failed
    to download (Google Fonts needs the network) stops the build instead of being replaced.
    """
    # Scale factor 2, as the former Puppeteer script used: with system fonts, Chromium
    # places text baselines one pixel differently at scale factor 1.
    context = browser.new_context(color_scheme="light", device_scale_factor=2)
    page = context.new_page()
    page.goto(html_path.as_uri(), wait_until="networkidle")
    page.evaluate("() => document.fonts.ready.then(() => true)")
    missing = [font for font in fonts if not page.evaluate("f => document.fonts.check(f)", font)]
    if missing:
        sys.exit(f"\nError: {html_path.name}: font(s) not loaded: {', '.join(missing)}. Check the network connection.")
    if fixed_page:
        # The designed CV is one fixed A4 page: content past its bottom edge would be cut off silently.
        page.emulate_media(media="print")
        overflow = page.evaluate(DESIGN_OVERFLOW)
        if overflow > 0.5:
            sys.exit(f"\nError: the designed CV does not fit on its A4 page: its content is {overflow:.0f} px "
                     f"(about {overflow / 14:.0f} lines) too long.\nShorten the content, or hide something from "
                     f"this version with `hide_in: [design]` in _cv/cv.yml.")
    data = page.pdf(prefer_css_page_size=True, print_background=True, tagged=True)
    context.close()
    # Chromium stamps the time into every PDF: keep the existing file when nothing else
    # changed, so that regenerating does not make git see a new PDF each time.
    if not pdf_path.exists() or without_dates(pdf_path.read_bytes()) != without_dates(data):
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(data)
    pages = page_count(data)
    if pages > 1:
        sys.exit(f"\nError: {pdf_path.relative_to(ROOT)} is {pages} pages long, the limit is 1.\n"
                 f"Shorten the content, or hide something from this version with `hide_in` in _cv/cv.yml.")
    return pdf_path


def make_share_image(browser, env, cv_page, out):
    """A card with a thumbnail of the CV page in its dark theme."""
    context = browser.new_context(viewport={"width": 794, "height": 1123}, device_scale_factor=2, color_scheme="dark")
    page = context.new_page()
    page.goto(cv_page.as_uri(), wait_until="networkidle")
    page.evaluate(OG_THUMBNAIL_STYLES)
    page.wait_for_timeout(300)
    LOCAL.mkdir(exist_ok=True)
    page.locator(".cv-container").screenshot(path=LOCAL / "og-thumb.png")
    context.close()

    card = write(LOCAL / "og-card.html", env.get_template("og.html.j2").render(thumb=(LOCAL / "og-thumb.png").as_uri()))
    context = browser.new_context(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    page = context.new_page()
    page.goto(card.as_uri(), wait_until="networkidle")
    page.evaluate("() => document.fonts.ready.then(() => true)")
    page.wait_for_timeout(250)
    data = page.screenshot()
    context.close()
    if not out.exists() or out.read_bytes() != data:
        out.write_bytes(data)
    return out


# ── Checks ──

def pdf_text(pdf):
    """Text of a PDF in content-stream order (`pdftotext -raw`), the strictest reading:
    it only separates words that are really separated on the page."""
    try:
        text = subprocess.run(["pdftotext", "-raw", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("\nError: the checks need pdftotext (package poppler-utils).")
    return re.sub(r"-\n", "-", text)  # a word broken after its hyphen at a line end is one word


def published_files():
    """Files GitHub Pages serves: tracked files outside `_` folders, plus the generated ones."""
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout
    paths = {ROOT / p for p in tracked.split() if not p.startswith(("_", "."))}
    paths |= set(PDFS.values()) | {ROOT / "cv" / "index.html"}
    return sorted(p for p in paths if p.exists() and p.suffix in {".html", ".css", ".js", ".md", ".txt", ".pdf"})


def check_outputs(cv):
    failures = []
    first = next(section for section in cv["sections"] if section.get("text"))
    for version, pdf in PDFS.items():
        summary = plain(first.get("classic_text", first["text"]) if version.startswith("classic") else first["text"])
        words = set(pdf_text(pdf).split())
        missing = [word for word in summary.split() if word not in words]
        if missing:
            failures.append(f"{pdf.relative_to(ROOT)}: summary words not found as such in the extracted text: "
                            f"{', '.join(missing)}")
    for path in published_files():
        text = pdf_text(path) if path.suffix == ".pdf" else path.read_text(errors="replace")
        found = [label for label, pattern in FORBIDDEN.items() if re.search(pattern, text)]
        if found:
            failures.append(f"{path.relative_to(ROOT)}: contains {', '.join(found)}")
    if failures:
        sys.exit("\nError: the outputs failed their checks:\n  " + "\n  ".join(failures))
    print(f"  checks: summary readable from the {len(PDFS)} PDFs; "
          f"{', '.join(FORBIDDEN)} absent from {len(published_files())} published files")


def main():
    cv = yaml.safe_load((HERE / "cv.yml").read_text())
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    env.filters.update(inline=inline, plain=plain, bare_url=bare_url)

    def classic_body(version):
        return Markup(keep_hyphenated_words_whole(
            env.get_template("classic_body.html.j2").render(cv=select(cv, version), dates=classic_dates)))

    def classic_page(version, paper):
        return write(LOCAL / f"{version}.html", env.get_template("classic.html.j2").render(
            cv=cv, paper=paper, body=classic_body(version), font_dir=(ROOT / "cv" / "fonts").as_uri()))

    # The CV page shows the designed CV and embeds both Classic versions as previews:
    # each preview is exactly the HTML printed into its PDF.
    page = write(ROOT / "cv" / "index.html", env.get_template("design.html.j2").render(
        cv=select(cv, "design-a4"), dates=design_dates, font_dir="fonts",
        classic_a4=classic_body("classic-a4"), classic_letter=classic_body("classic-letter"),
        pdfs={version: pdf.name for version, pdf in PDFS.items()}))
    classic_a4, classic_letter = classic_page("classic-a4", "A4"), classic_page("classic-letter", "Letter")

    outputs = [page]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        outputs.append(print_pdf(browser, page, PDFS["design-a4"], fixed_page=True,
                                 fonts=("800 26px 'Schibsted Grotesk'", "500 10px 'IBM Plex Mono'")))
        cmu = ("400 14px 'CMU Serif'", "700 14px 'CMU Serif'", "italic 400 14px 'CMU Serif'")
        outputs.append(print_pdf(browser, classic_a4, PDFS["classic-a4"], fonts=cmu))
        outputs.append(print_pdf(browser, classic_letter, PDFS["classic-letter"], fonts=cmu))
        outputs.append(make_share_image(browser, env, page, ROOT / "figures" / "og-cv.png"))
        browser.close()

    for path in outputs:
        print(f"  -> {path.relative_to(ROOT)}")
    check_outputs(cv)


if __name__ == "__main__":
    main()
