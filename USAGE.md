# How to use and change the reading builds

Two extra outputs sit next to the normal LaTeX layouts. Nothing else in the
template changes: `[twocolumn]` (bioRxiv look) and `[submit]` (journal look) still
build exactly as before.

| Output | What it is | Best for |
| --- | --- | --- |
| `00_Article_Narrow.pdf` | same manuscript, 110 x 180 mm single column | reading in a slim PDF pane, printing |
| `00_Article_Narrow.html` | one self-contained file that reflows | peeking at the text in a browser/editor pane, any width |

## 1. Build

Everything goes through `build.py` (Python, no bash needed — a VS Code task cannot
find git-bash on the Windows PATH, which is why a `.sh`-only driver fails with
"File not found"):

```bash
python build.py            # HTML only  <- the default, ~0.5-2 s
python build.py all        # narrow PDF + HTML, ~9 s
python build.py pdf        # only the narrow PDF
python build.py clean      # delete generated files
python build.py watch      # on every save: rebuild the HTML (default)
python build.py watch all  # on every save: rebuild the PDF too
```

The default is HTML because that is what you read while writing: it is 5x faster
and, with LaTeX Workshop installed, the PDF is already rebuilt by the editor on
save (see below).

Equivalent entry points, all calling the same file:

- VS Code: **Ctrl+Shift+B** -> "Build all (narrow PDF + HTML)"
- VS Code: `Ctrl+Shift+P` -> `Tasks: Run Task` -> "Watch: rebuild on every save"
- Windows Explorer: double-click `build.cmd`
- git-bash / WSL: `./build.sh`

## 2. Watch mode (rebuild while you write)

`python build.py watch` (or the VS Code task above) builds immediately, then
watches `*.tex`, `*.bib`, `theme/*.cls`, `theme/*.bst`, `html/*.css`. When you save,
it waits for the writes to settle, rebuilds the PDF and then the HTML, and prints
which files changed:

```
[16:18:26] changed: 01_Article_MainText.tex -> rebuilding
PDF   : 00_Article_Narrow.pdf  13 pages  311.811 x 510.236 pts
HTML  : 00_Article_Narrow.html  87 KB
```

Leave it running in a VS Code terminal panel. A failed LaTeX run does not stop the
watcher: the error is printed and it keeps watching for the next save.

## 2b. If you have the LaTeX Workshop extension (you do)

`james-yu.latex-workshop` rebuilds the PDF by itself when you save — that is why
`00_Article_Narrow.pdf` gets a new timestamp even when `build.py` only built the
HTML. So the two "auto" mechanisms divide the work:

| what | who rebuilds it |
| --- | --- |
| `00_Article_Narrow.pdf` | LaTeX Workshop, on save (already set up) |
| `00_Article_Narrow.html` | `python build.py watch` (HTML only) |

Do not run `python build.py watch all` on top of that: the PDF would be built
twice on every save. If you would rather have one process own everything, turn
LaTeX Workshop's auto build off (`"latex-workshop.latex.autoBuild.run": "never"`
in `.vscode/settings.json`) and use `python build.py watch all`.

Known annoyance: LaTeX Workshop builds whichever file it thinks is the root. If
it keeps building the A4 `00_Article_Merge.tex`, put a magic comment at the top of
your section file, `% !TEX root = 00_Article_Narrow.tex`, so it builds the reading
version instead.

## 3. Where to change what

| I want to change | File and place | Current value |
| --- | --- | --- |
| narrow page size | `theme/bioRxiv.cls` lines 91-93, `\if@narrow` branch of `geometry` | `paperwidth=110mm, paperheight=180mm` |
| side margins of the narrow page | same `geometry` call, `left=6mm,right=6mm` | 6 mm |
| room for the page number | same file line 597 `\footskip=5mm` (must stay smaller than `bottom`) | 5 mm |
| title size on the narrow page | `theme/bioRxiv.cls`, `\@maketitle`, `{\Large\bfseries\@title ...}` | `\Large` (12 pt) |
| base text size of the narrow PDF | master file: add a size to the class options, e.g. `\documentclass[11pt,submit,narrow]{theme/bioRxiv}` (13 pages at 10 pt, 15 at 11 pt in this demo) | 10 pt |
| HTML text size | `html/manuscript.css` line 39 `html { font-size: 16px }` | 16 px, never scaled by the window |
| HTML line length | `html/manuscript.css` line 11 `--measure: 40rem` | 40 rem |
| HTML colours | `html/manuscript.css` lines 6-11 (light) and the `[data-theme="dark"]` block | see file |
| which sections are included | `00_Article_Narrow.tex` lines 45-48 (`\include{...}`) | all four |
| dark / light in the browser | append `?theme=dark` or `?theme=auto` to the HTML URL | light |
| a table that is too wide | wrap the `tabular` in `\narrowfit{...}` (see `04_Article_SupplementaryTables.tex`) | no-op in the other layouts |

Recommended page widths for the narrow PDF: `90mm` (very slim pane), `110mm`
(default), `120mm` (more comfortable), `148mm` (A5, tablet). Changing the width
does not require touching anything else — save, and watch mode rebuilds it.

## 4. FAQ

**VS Code: "The terminal process failed to launch: File not found".**
Fixed: the tasks now call `python build.py` instead of `bash build.sh`. If you still
see it, `Tasks: Run Task` -> pick a task explicitly, and check `python --version`
works in the VS Code terminal.

**The HTML looks inverted / black in VS Code.**
It is light by default now. If you see dark, you are opening an old copy or a URL
with `?theme=auto`.

**"Figure [fig:cells]" instead of a number in the HTML.**
The `.aux` files were missing: run `python build.py pdf` (or `python build.py all`)
once. Only a PDF build updates the numbers, so a brand-new figure stays `[label]`
until then.

**A table runs off the narrow PDF page.**
Wrap it in `\narrowfit{...}`; the other two layouts ignore that macro, so the
shared section file still builds all three versions.

**The build fails with `! LaTeX Error: Missing \begin{document}`.**
An `\if`/`\fi` in the class file got unbalanced. `git diff theme/bioRxiv.cls`
shows what changed; `git checkout -- theme/bioRxiv.cls` restores the released
version (you then lose the `narrow` option).

**I only want the normal paper, not the reading builds.**
Ignore `00_Article_Narrow.tex`, `build.py`, `build.sh`, `build.cmd`, `tools/`,
`html/`, `USAGE.md` and build `00_Article_Merge.tex` as you always did.
