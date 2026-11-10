# manuscript-templates
LaTeX templates for manuscripts (switchable bioRxiv preprint and journal submission templates), for use on Overleaf.

## Basic idea

An ideal manuscript LaTeX template should be able to generate two versions of the manuscript:

1. a preprint version - typeset to look like a finished paper
2. a journal submission version - better for reviewing, with line numbers and different spacing, etc.

The ideal template should be able to switch between these two manuscript layouts. A preview of both outputs is shown below.

## Use

Day-to-day usage of the reading builds (how to build, where to change the page
size / font size / theme): see [USAGE.md](USAGE.md).

To use, just clone this repo and import into Overleaf or a directory on your own computer to use a local LaTeX installation.
The following files and folders are not required: `img`, `examples`, `README.md`, `LICENSE`.

Write your manuscript in `01_Article_MainText.tex` and then comment either line 2 or 3 of `00_Article_Merge.tex` to select between outputs.
There are optional Supplementary tex files that can also be edited.
If they are not required, comment the appropriate lines in `00_Article_Merge.tex`.

Tested on Overleaf - TeXLive 2025 with pdfLaTeX compiler.


## Narrow preview version (side-by-side writing)

When you write with the compiled PDF open next to the source (a vertical split
narrower than a quarter of the screen), a full A4 page scaled to fit is unreadable.
The class therefore has a `narrow` option: it typesets the same manuscript on a
110 mm x 180 mm single-column page, so fit-to-width stays at about 100% and the
text keeps its designed size.

`00_Article_Narrow.tex` is the master file for it:

```latex
\documentclass[submit,narrow]{theme/bioRxiv}
```

Build with:

```bash
python build.py all          # narrow PDF + HTML (or: latexmk -pdf 00_Article_Narrow.tex)
```

What `narrow` changes — and only when the option is given, the preprint and
submission layouts are untouched:

- page 110 mm x 180 mm, 6 mm side margins, single column
- no line numbers, no forced page break before every section, hyphenation kept on
  (a short measure needs it to avoid rivers of white space)
- smaller title/heading/caption sizes, minimal footer (page number only)
- images without an explicit width are capped to the column width
- `\raggedbottom`, because stretched vertical glue looks bad on a short page

For a table that is too wide, wrap the table body in `\narrowfit{...}` (provided by
`adjustbox` in `00_Article_Narrow.tex`) so it scales down to the column instead of
running off the page. To change the page size, edit the `geometry` options in the
`narrow` branch of `theme/bioRxiv.cls`.

## HTML reading version (reflows to any pane width)

The narrow PDF has a fixed page; the HTML version reflows instead, so one file
stays readable at *any* pane width — a quarter-screen split, a browser tab, a
phone — with no recompiling and no zooming.

```bash
python build.py        # HTML only - the default, ~1 s
python build.py all    # PDF first (numbers \ref/\cref), then the HTML
```

Output: `00_Article_Narrow.html`, a single self-contained file (CSS and images
embedded), so it opens straight from disk in VS Code's Simple Browser / Live
Preview or any browser. `python build.py clean` removes it.

Pipeline and what it does:

- `tools/tex2html.py` inlines the `\include`d sections (pandoc does not follow
  `\include`), lifts the title/author/abstract/keywords block into pandoc
  metadata, unwraps `\narrowfit{...}`, drops PDF-only plumbing (`\lfoot`,
  `\setcounter`, `\fancyhead`, ...) and replaces the demo `\lipsum`.
- cross-references are taken from the LaTeX `.aux` files, so
  `Figure \ref{...}` prints the number LaTeX assigned — including `S1`/`SV1`
  for supplementary items. Without `.aux` files you get `[label]` instead.
- pandoc (>= 3) converts with `--citeproc` + `refs.bib` for citations and MathML
  for equations, then `html/manuscript.css` styles it: fixed 16 px type (never
  scaled by the viewport), `hyphens: auto`, `max-width` measure, tables that
  scroll locally instead of pushing the page sideways, dark-mode support.

Colour scheme: the page is **light by default**, on purpose — a preview pane in a
dark editor (VS Code webview, Live Preview) reports `prefers-color-scheme: dark`,
and letting the CSS follow it turns the paper black while you are reading it next
to a white PDF. Dark is opt-in through the URL:

| URL | Result |
| --- | --- |
| `.../00_Article_Narrow.html` | white paper (default) |
| `.../00_Article_Narrow.html?theme=dark` | dark, explicit |
| `.../00_Article_Narrow.html?theme=auto` | follow the OS/editor setting |

Known differences from the PDF layouts (inherent to the pandoc route):

- figure/table captions are printed without a number ("Figure 1." is not
  generated); the in-text references still carry the correct numbers;
- `\SI`/`\si` units are expanded by a small shim, not by siunitx, so unusual
  unit macros may come out as their raw name;
- no line numbers, no figure floats — content order is source order.

## Contributions

The initial overleaf template was forked from the template created by Henriques lab [available here](https://www.overleaf.com/latex/templates/henriqueslab-biorxiv-template/nyprsybwffws).
This is a modification of the PNAS template (also available on Overleaf) which is widely used on bioRxiv.
We have made a few changes to the HenriquesLab bioRxiv template and made it possible to easily generate a journal submission version.

Changes include:

- genuine bioRxiv logo used in the footer
- support for ORCiDs using `\orcidlink`
- Helvetica for readability
- greater range of custom units
- simplified directory structure

## What do they look like?

### Preprint version (for bioRxiv)

![img](img/Example_bioRxiv.jpg?raw=true "image")

### Journal submission version

![img](img/Example_submit.jpg?raw=true "image")


## Further details

The provided files (with comments) provide guidance on how to put your manuscript together.
There are a few things to be aware of:

- the manuscript is compiled from separate `.tex` files which are listed in `00_Article_Merge.tex`. The first included `.tex` file is the main text (`01_Article_MainText.tex`) and this has its own reference section, which means that a subsequent "Supplementary Information" section will have a separate reference section.
- switching from the preprint version (`\documentclass[twocolumn]{bioRxiv}`) to the plain manuscript version (`\documentclass[submit]{bioRxiv}`) works well, but has some foibles. Any figures that use `figure{}` environment rather than `figure*{}` may need resizing by a factor of 0.5 to remain at the intended size.
- figures should be prepared as a single file and placed in the `figures` folder - use of figures compiled from multiple files in LaTeX is not supported.