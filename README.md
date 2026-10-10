# baillietn.github.io

Personal portfolio and CV website for Nicolas Bailliet — LLM / Deep Learning — model training & inference.

## Project Structure

```
.
├── index.html, style.css               # Portfolio page (hand-written)
├── cv/
│   ├── index.html                      # CV page, GENERATED: do not edit by hand
│   ├── style.css                       # CV page styles
│   └── cv-nicolas-bailliet.pdf         # GENERATED PDF
├── figures/                            # Images
├── _cv/                                # CV source and generator
│   ├── cv.yml                          # CV content: the only place to edit the CV
│   ├── templates/                      # HTML templates (Jinja2)
│   ├── generate.py                     # Generator
│   └── local/                          # Git-ignored: intermediate files
└── generate-cv.sh                      # Regenerates everything
```

## Editing the CV

Edit `_cv/cv.yml`, then run `./generate-cv.sh` and commit the generated files.

The first run creates a Python environment in `.venv/` and downloads Chromium.

Adding an item to a list (a job, a project, a skill, a bullet) or a whole section under
`sections:` needs no template change: see the comments at the top of `_cv/cv.yml`.

`_cv/` starts with an underscore on purpose: GitHub Pages does not publish such folders,
so the CV source and the generator stay out of the public site.
