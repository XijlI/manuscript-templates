#!/usr/bin/env python3
"""Build driver for the manuscript reading builds.

    python build.py            HTML only (default, ~5 s)
    python build.py html       HTML only
    python build.py pdf        narrow PDF only
    python build.py all        narrow PDF + HTML
    python build.py watch      rebuild the default (HTML) whenever a file is saved
    python build.py watch all  same, but rebuild the PDF too (refreshes refs)
    python build.py clean      remove everything generated

Windows-native on purpose: VS Code tasks inherit the Windows PATH, where a
git-bash `bash` may not exist, so a .sh driver breaks with
"The terminal process could not be launched: File not found". Python, latexmk
and pandoc are all on PATH here, so this file is the single source of truth;
build.sh / build.cmd are one-line wrappers around it.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MASTER = "00_Article_Narrow"
PDF = ROOT / f"{MASTER}.pdf"
HTML = ROOT / f"{MASTER}.html"
BUILD = ROOT / "build"

WATCH_GLOBS = ("*.tex", "*.bib", "theme/*.cls", "theme/*.bst", "html/*.css")
WATCH_IGNORE = ("00_Article_Merge.tex", "00_Article_TwoCol.tex")


# --------------------------------------------------------------------- helpers
def run(cmd: list[str], *, check: bool = True) -> int:
    print("$", " ".join(cmd), flush=True)
    code = subprocess.call(cmd, cwd=ROOT)
    if check and code != 0:
        raise SystemExit(f"command failed ({code}): {' '.join(cmd)}")
    return code


def need(program: str, hint: str) -> str:
    path = shutil.which(program)
    if not path:
        raise SystemExit(f"{program} not found on PATH — {hint}")
    return path


# ----------------------------------------------------------------------- steps
def build_pdf() -> None:
    latexmk = need("latexmk", "install MiKTeX (it ships latexmk)")
    run([latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"{MASTER}.tex"])

    pages = size = "?"
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("Pages:"):
                pages = line.split(":", 1)[1].strip()
            elif line.startswith("Page size:"):
                size = line.split(":", 1)[1].strip()
    print(f"PDF   : {PDF.name}  {pages} pages  {size}", flush=True)


def build_html() -> None:
    pandoc = need("pandoc", "install pandoc from pandoc.org, or `winget install JohnMacFarlane.Pandoc`")
    if not any(ROOT.glob("*.aux")):
        print(
            "note: no .aux files yet — cross-references will show as [label]. "
            "Run `python build.py pdf` first.",
            flush=True,
        )

    run([sys.executable, str(ROOT / "tools" / "tex2html.py"), f"{MASTER}.tex", "-o", str(BUILD / "flat.tex")])
    run(
        [
            pandoc,
            str(BUILD / "flat.tex"),
            "--from", "latex",
            "--to", "html5",
            "--standalone",
            "--embed-resources",
            "--math-method=mathml",
            "--wrap=none",
            "--citeproc",
            "--bibliography=refs.bib",
            "--metadata", "reference-section-title=References",
            "--css=html/manuscript.css",
            f"--metadata-file={BUILD / 'flat.tex.front.yaml'}",
            "--metadata", "link-citations=true",
            "--output", str(HTML),
        ]
    )
    inject_theme_switch(HTML)
    print(f"HTML  : {HTML.name}  {HTML.stat().st_size / 1024:.0f} KB", flush=True)


def inject_theme_switch(path: Path) -> None:
    """Light paper by default; ?theme=dark / ?theme=auto opt in.

    A dark editor webview reports prefers-color-scheme: dark, which would
    otherwise render the whole paper inverted. Keyed on our own script text
    because pandoc's template already ships a viewport meta.
    """
    html = path.read_text(encoding="utf-8")
    if 'get("theme")' in html:
        return
    head = (
        "<head>\n"
        '<meta name="color-scheme" content="light">\n'
        "<script>\n"
        "(function () {\n"
        '  var t = new URLSearchParams(location.search).get("theme");\n'
        '  if (t === "dark" || t === "auto") {\n'
        "    document.documentElement.dataset.theme = t;\n"
        '    if (t === "dark") {\n'
        "      var m = document.querySelector('meta[name=\"color-scheme\"]');\n"
        '      if (m) m.setAttribute("content", "dark");\n'
        "    }\n"
        "  }\n"
        "})();\n"
        "</script>"
    )
    path.write_text(html.replace("<head>", head, 1), encoding="utf-8")


def clean() -> None:
    removed = []
    if shutil.which("latexmk") and (ROOT / f"{MASTER}.tex").exists():
        subprocess.call(
            ["latexmk", "-C", f"{MASTER}.tex"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    for p in sorted(ROOT.glob(f"{MASTER}.*")):
        if p.suffix in {".tex"}:
            continue  # never delete sources
        if p.exists():
            p.unlink()
            removed.append(p.name)
    for d in (BUILD,):
        if d.exists():
            shutil.rmtree(d)
            removed.append(d.name + "/")
    print("cleaned: " + (", ".join(removed) if removed else "nothing to remove"))


def build_target(target: str) -> None:
    """all = PDF then HTML (order matters: .aux from the PDF feed the refs)."""
    if target in {"all", "pdf"}:
        build_pdf()
    if target in {"all", "html"}:
        build_html()


# ----------------------------------------------------------------------- watch
def sources() -> list[Path]:
    files: list[Path] = []
    for pattern in WATCH_GLOBS:
        for p in ROOT.glob(pattern):
            if p.is_file() and p.name not in WATCH_IGNORE:
                files.append(p)
    return files


def snapshot() -> dict[str, float]:
    return {str(p): p.stat().st_mtime for p in sources()}


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


LOCK = BUILD / ".watch.pid"


def acquire_watch_lock() -> bool:
    """Only one watcher at a time: two of them rebuild twice and fight over files."""
    BUILD.mkdir(exist_ok=True)
    # O_EXCL makes the create atomic: two watchers started at the same moment
    # would otherwise both pass the "is it there?" check.
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                other = int(LOCK.read_text(encoding="utf-8").strip())
            except ValueError:
                other = 0
            if other and _pid_alive(other):
                print(
                    f"a watcher is already running (pid {other}). Stop it first "
                    "(Ctrl+C in its terminal), or delete build/.watch.pid if it is stale.",
                    file=sys.stderr,
                )
                return False
            LOCK.unlink(missing_ok=True)   # stale lock from a killed process
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        return True
    print("could not take the watch lock", file=sys.stderr)
    return False


def watch(target: str = "html") -> None:
    print(f"watching for saves (Ctrl+C to stop) — rebuilding: {target}", flush=True)
    for pattern in WATCH_GLOBS:
        print("  ", pattern, flush=True)
    if target == "html":
        print(
            "note: HTML only uses the .aux from the last PDF build, so new "
            "figures/tables may show [label] until you run `python build.py pdf` "
            "or use `python build.py watch all`.",
            flush=True,
        )
    state = snapshot()
    print(f"initial build at {time.strftime('%H:%M:%S')}", flush=True)
    build_target(target)
    atexit.register(lambda: LOCK.unlink(missing_ok=True))

    while True:
        time.sleep(1.0)
        now = snapshot()
        changed = [k for k, v in now.items() if state.get(k) != v]
        if not changed:
            continue
        # debounce: editors write in bursts (autosave, formatters)
        while True:
            time.sleep(0.8)
            nxt = snapshot()
            if nxt == now:
                break
            now = nxt
        state = now
        names = ", ".join(Path(c).name for c in sorted(changed))
        print(f"\n[{time.strftime('%H:%M:%S')}] changed: {names} -> rebuilding", flush=True)
        try:
            build_target(target)
        except SystemExit as exc:
            print(f"build failed: {exc}", flush=True)


# ------------------------------------------------------------------------ main
def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "html").lower()
    if target in {"-h", "--help", "help"}:
        print((__doc__ or "").strip())
        return 0

    if target == "clean":
        clean()
        return 0
    if target == "watch":
        if not acquire_watch_lock():
            return 1
        sub = (sys.argv[2] if len(sys.argv) > 2 else "html").lower()
        if sub not in {"html", "pdf", "all"}:
            print(f"watch target must be html|pdf|all, got {sub}", file=sys.stderr)
            return 2
        try:
            watch(sub)
        except KeyboardInterrupt:
            print("\nwatch stopped")
        return 0
    if target in {"all", "pdf", "html"}:
        build_target(target)
        if target in {"all", "pdf"}:
            print("\nnarrow PDF :", PDF, flush=True)
        if target in {"all", "html"}:
            print("\nHTML       :", HTML, flush=True)
        return 0

    print(f"unknown target: {target} (use all|pdf|html|clean|watch)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
