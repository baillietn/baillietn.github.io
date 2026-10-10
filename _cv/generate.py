#!/usr/bin/env python3
"""Generate the CV from _cv/cv.yml. Run it through ./generate-cv.sh

Outputs:
  cv/index.html                 the CV page
  cv/cv-nicolas-bailliet.pdf    the CV page printed on A4
  figures/og-cv.png             the share image (loads its fonts from Google Fonts)
"""
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOCAL = HERE / "local"  # git-ignored: intermediate files

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


def inline(text):
    """Escape text, then turn **bold** into <strong>."""
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text))))


def parse_date(value):
    """'2025-06' -> (2025, 6); 'present' -> None."""
    if value == "present":
        return None
    year, _, month = str(value).partition("-")
    return int(year), int(month) if month else None


def design_dates(start, end):
    """Date range on the design CV: months within one year ('Jun-Aug 2025'), years otherwise ('2023–Present')."""
    s, e = parse_date(start), parse_date(end)
    if e and s[0] == e[0] and s[1] and e[1]:
        return f"{MONTHS[s[1] - 1]}-{MONTHS[e[1] - 1]} {s[0]}"
    return f"{s[0]}–{e[0] if e else 'Present'}"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def without_dates(pdf_bytes):
    return re.sub(rb"/(CreationDate|ModDate) \(D:[^)]*\)", b"", pdf_bytes)


def print_pdf(browser, html_path, pdf_path):
    """Print a page to PDF; paper size and margins come from the page's own CSS."""
    # Scale factor 2, as the former Puppeteer script used: with system fonts, Chromium
    # places text baselines one pixel differently at scale factor 1.
    context = browser.new_context(color_scheme="light", device_scale_factor=2)
    page = context.new_page()
    page.goto(html_path.as_uri(), wait_until="networkidle")
    page.evaluate("() => document.fonts.ready.then(() => true)")
    data = page.pdf(prefer_css_page_size=True, print_background=True)
    context.close()
    # Chromium stamps the time into every PDF: keep the existing file when nothing else
    # changed, so that regenerating does not make git see a new PDF each time.
    if not pdf_path.exists() or without_dates(pdf_path.read_bytes()) != without_dates(data):
        pdf_path.write_bytes(data)
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
    env.filters["inline"] = inline

    page = write(ROOT / "cv" / "index.html", env.get_template("design.html.j2").render(cv=cv, dates=design_dates))
    outputs = [page]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        outputs.append(print_pdf(browser, page, ROOT / "cv" / "cv-nicolas-bailliet.pdf"))
        outputs.append(make_share_image(browser, env, page, ROOT / "figures" / "og-cv.png"))
        browser.close()

    for path in outputs:
        print(f"  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
