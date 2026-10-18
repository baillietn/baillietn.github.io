# baillietn.github.io

Personal portfolio and CV website for Nicolas Bailliet — LLM / Deep Learning — model training & inference.

## Project Structure

```
.
├── index.html, style.css                   # Portfolio page (hand-written)
├── cv/
│   ├── index.html                          # CV page, GENERATED: do not edit by hand
│   ├── style.css                           # CV page styles
│   ├── fonts/                              # CMU Serif for the Classic CV (SIL OFL)
│   ├── cv-nicolas-bailliet.pdf             # GENERATED: designed CV, A4
│   ├── cv-nicolas-bailliet-classic-a4.pdf  # GENERATED: Classic CV, A4
│   └── cv-nicolas-bailliet-classic-letter.pdf  # GENERATED: Classic CV, US Letter
├── figures/                                # Images
├── _cv/                                    # CV source and generator
│   ├── cv.yml                              # CV content: the only place to edit the CV
│   ├── templates/                          # HTML templates (Jinja2)
│   ├── generate.py                         # Generator
│   └── local/                              # Git-ignored: intermediate files
└── generate-cv.sh                          # Regenerates everything
```

## Editing the CV

Edit `_cv/cv.yml`, then run `./generate-cv.sh` and commit the generated files.
The first run creates a Python environment in `.venv/` and downloads Chromium.

Everything comes from the same file, and every version fits on one page:

| Version | Output | Layout |
|---|---|---|
| `design-a4` | `cv/index.html`, `cv/cv-nicolas-bailliet.pdf` | designed, with photo, A4 |
| `classic-a4` | `cv/cv-nicolas-bailliet-classic-a4.pdf` | Classic: sober, one column, LaTeX style, A4 |
| `classic-letter` | `cv/cv-nicolas-bailliet-classic-letter.pdf` | Classic, US Letter |

The CV page shows the Design version by default, and the Classic one in A4 or US Letter
with the switches at the top. The URL follows the choice, so a link can open one version
directly: `cv/?style=classic&paper=letter`.

Adding an item to a list (a job, a project, a skill, a bullet) or a whole section under
`sections:` needs no template change: see the comments at the top of `_cv/cv.yml`.
`hide_in: [classic]` on an item leaves it out of both Classic versions; a version name
(`design-a4`, `classic-a4`, `classic-letter`) targets one version.

The generator stops with a message if a version no longer fits on one page, if a web font
did not load (the designed CV uses Google Fonts, so generating it needs a network
connection), or if a check fails: the summary must read back word for word from the text
of each PDF (`pdftotext`, package poppler-utils), and some words must not appear on the
site.

`_cv/` starts with an underscore on purpose: GitHub Pages does not publish such folders,
so the CV source and the generator stay out of the public site.
