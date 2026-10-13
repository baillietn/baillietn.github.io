#!/usr/bin/env python3
"""Generate every version of the CV from _cv/cv.yml. Run it through ./generate-cv.sh

Published (commit them):
  cv/index.html                           the CV page: designed CV, with a preview of the US Letter one
  cv/cv-nicolas-bailliet.pdf              designed CV, A4
  cv/cv-nicolas-bailliet-us-letter.pdf    plain one-column CV, US Letter, one page
  figures/og-cv.png                       the share image (loads its fonts from Google Fonts)

Local only (git-ignored):
  _cv/local/cv-nicolas-bailliet-ats.pdf   plain one-column CV with all the content, A4

In cv.yml, `hide_in: [letter]` on an entry, a bullet, a skill or a whole section leaves it
out of a version; the versions are `design`, `letter` and `ats`.
"""
import copy
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOCAL = HERE / "local"  # git-ignored: the ATS version and intermediate files

VERSIONS = ("design", "letter", "ats")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

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
    """The content as one version sees it: list items whose `hide_in` names the version are dropped."""
    def walk(node, where):
        if isinstance(node, dict):
            return {key: walk(value, f"{where}.{key}") for key, value in node.items() if key != "hide_in"}
        if isinstance(node, list):
            kept = []
            for index, item in enumerate(node):
                hidden = item.get("hide_in", []) if isinstance(item, dict) else []
                unknown = set(hidden) - set(VERSIONS)
                if unknown:
                    sys.exit(f"cv.yml {where}[{index}]: hide_in names unknown version(s) {', '.join(sorted(unknown))}; "
                             f"use {', '.join(VERSIONS)}")
                if version in hidden:
                    continue
                item = walk(item, f"{where}[{index}]")
                # A bullet written as {text, hide_in} is a plain string once hide_in is resolved.
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


def design_dates(start, end):
    """Date range on the designed CV: months within one year ('Jun–Aug 2025'), years otherwise ('2023–Present')."""
    s, e = parse_date(start), parse_date(end)
    if e and s[0] == e[0] and s[1] and e[1]:
        return f"{MONTHS[s[1] - 1]}–{MONTHS[e[1] - 1]} {s[0]}"
    return f"{s[0]}–{e[0] if e else 'Present'}"


def plain_dates(start, end):
    """Date range on the plain CVs, one format everywhere: 'Jun 2025 – Aug 2025', 'Sep 2023 – Present'."""
    def fmt(value):
        date = parse_date(value)
        if date is None:
            return "Present"
        return f"{MONTHS[date[1] - 1]} {date[0]}" if date[1] else str(date[0])

    return f"{fmt(start)} – {fmt(end)}"


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


def print_pdf(browser, html_path, pdf_path, max_pages=None, fixed_page=False, fonts=()):
    """Print a page to PDF; paper size and margins come from the page's own CSS.

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
    if max_pages and pages > max_pages:
        sys.exit(f"\nError: {pdf_path.relative_to(ROOT)} is {pages} pages long, the limit is {max_pages}.\n"
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


def main():
    cv = yaml.safe_load((HERE / "cv.yml").read_text())
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    env.filters.update(inline=inline, plain=plain, bare_url=bare_url)

    def plain_body(version):
        return Markup(keep_hyphenated_words_whole(
            env.get_template("plain_body.html.j2").render(cv=select(cv, version), dates=plain_dates)))

    def plain_page(version, paper):
        return write(LOCAL / f"{version}.html", env.get_template("plain.html.j2").render(
            cv=cv, paper=paper, body=plain_body(version)))

    # The CV page shows the designed CV and embeds the US Letter one as a preview.
    page = write(ROOT / "cv" / "index.html", env.get_template("design.html.j2").render(
        cv=select(cv, "design"), dates=design_dates, letter_body=plain_body("letter")))
    letter, ats = plain_page("letter", "Letter"), plain_page("ats", "A4")

    outputs = [page]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        outputs.append(print_pdf(browser, page, ROOT / "cv" / "cv-nicolas-bailliet.pdf", max_pages=1, fixed_page=True,
                                 fonts=("800 26px 'Schibsted Grotesk'", "500 10px 'IBM Plex Mono'")))
        outputs.append(print_pdf(browser, letter, ROOT / "cv" / "cv-nicolas-bailliet-us-letter.pdf", max_pages=1))
        outputs.append(print_pdf(browser, ats, LOCAL / "cv-nicolas-bailliet-ats.pdf"))
        outputs.append(make_share_image(browser, env, page, ROOT / "figures" / "og-cv.png"))
        browser.close()

    for path in outputs:
        print(f"  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
