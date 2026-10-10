# baillietn.github.io

Personal portfolio and CV website for Nicolas Bailliet — LLM / Deep Learning — model training & inference.

## Project Structure

```
.
├── index.html, style.css                   # Portfolio page (hand-written)
├── cv/
│   ├── index.html                          # CV page, GENERATED: do not edit by hand
│   ├── style.css                           # CV page styles
│   ├── cv-nicolas-bailliet.pdf             # GENERATED: designed CV, A4
│   └── cv-nicolas-bailliet-us-letter.pdf   # GENERATED: plain one-page CV, US Letter
├── figures/                                # Images
├── _cv/                                    # CV source and generator
│   ├── cv.yml                              # CV content: the only place to edit the CV
│   ├── templates/                          # HTML templates (Jinja2)
│   ├── generate.py                         # Generator
│   └── local/                              # Git-ignored: the ATS version, intermediate files
└── generate-cv.sh                          # Regenerates everything
```

## Editing the CV

Edit `_cv/cv.yml`, then run `./generate-cv.sh` and commit the generated files.
The first run creates a Python environment in `.venv/` and downloads Chromium.

Everything comes from the same file:

| Version | Output | Layout |
|---|---|---|
| `design` | `cv/index.html`, `cv/cv-nicolas-bailliet.pdf` | designed, with photo, A4, one page |
| `letter` | `cv/cv-nicolas-bailliet-us-letter.pdf`, previewed on the CV page | plain, one column, US Letter, one page |
| `ats` | `_cv/local/cv-nicolas-bailliet-ats.pdf` (never committed) | plain, one column, A4, all the content |

Adding an item to a list (a job, a project, a skill, a bullet) or a whole section under
`sections:` needs no template change: see the comments at the top of `_cv/cv.yml`.
`hide_in: [letter]` on an item leaves it out of a version.

The generator stops with a message if the designed CV no longer fits on its A4 page or
if the US Letter CV exceeds one page.

`_cv/` starts with an underscore on purpose: GitHub Pages does not publish such folders,
so the CV source and the generator stay out of the public site.
