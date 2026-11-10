#!/usr/bin/env python3
"""Flatten the LaTeX manuscript into one file pandoc can read.

Why this exists: pandoc's LaTeX reader does not follow \\include, does not know
this template's class macros (\\leadauthor, \\affil, \\corrauthor, \\narrowfit),
and cannot number \\ref/\\cref. So we inline the section files, lift the title
block into pandoc metadata, drop the macros only the PDF layouts need, and hand
pandoc plain LaTeX plus a few shims.

Usage:  python tools/tex2html.py 00_Article_Narrow.tex -o build/flat.tex
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INCLUDE = re.compile(r"^\s*\\(?:include|input)\{([^}]+)\}", re.M)

# Lines that are PDF-layout plumbing: useless or fatal for pandoc.
PLUMBING = re.compile(
    r"^\s*\\(?:onecolumn|twocolumn|clearpage|newpage|pagebreak|nopagebreak|"
    r"fancyhead|fancyfoot|lfoot|rfoot|lhead|rhead|thispagestyle|pagestyle|"
    r"captionsetup|setcounter|addtocounter|setlength|vspace|vskip|hspace|"
    r"hyphenation|sisetup|bibliography|bibliographystyle|renewcommand|"
    r"providecommand|DeclareSIUnit|linenumbers|nolinenumbers|maketitle|"
    r"leadauthor|shorttitle|affil|author|title|date|centering|raggedright|"
    r"raggedleft|raggedbottom|flushbottom|bigskip|medskip|smallskip|noindent|"
    r"makeatletter|makeatother|vfill)\b.*$",
    re.M,
)

# The demo template fills the body with \lipsum; pandoc cannot run it and a
# reader should see real prose, so substitute a canned paragraph.
LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat."
)

SHIM = r"""
%% --- shims so pandoc's LaTeX reader produces sensible text --------------
\newcommand{\leadauthor}[1]{}
\newcommand{\shorttitle}[1]{}
\newcommand{\affil}[2][]{}
\newcommand{\orcidlink}[1]{}
\newcommand{\narrowfit}[1]{#1}
\newcommand{\at}{@}
%% siunitx: pandoc has no siunitx support, so expand the basic unit macros
\newcommand{\SI}[2]{#1~#2}
\newcommand{\si}[1]{#1}
\newcommand{\num}[1]{#1}
\newcommand{\micro}{\textmu}
\newcommand{\meter}{m}
\newcommand{\milli}{m}
\newcommand{\centi}{c}
\newcommand{\kilo}{k}
\newcommand{\second}{s}
\newcommand{\minute}{min}
\newcommand{\hour}{h}
\newcommand{\day}{d}
\newcommand{\year}{yr}
\newcommand{\per}{/}
\newcommand{\cubic}{^3}
\newcommand{\square}{^2}
\newcommand{\gram}{g}
\newcommand{\liter}{L}
\newcommand{\litre}{L}
\newcommand{\volt}{V}
\newcommand{\watt}{W}
\newcommand{\hertz}{Hz}
\newcommand{\newton}{N}
\newcommand{\joule}{J}
\newcommand{\kelvin}{K}
\newcommand{\degree}{deg}
\newcommand{\celsius}{degC}
\newcommand{\mole}{mol}
\newcommand{\pixel}{px}
\newcommand{\rpm}{rpm}
\newcommand{\angstrom}{\AA}
\newcommand{\deci}{d}
\newcommand{\nano}{n}
\newcommand{\pico}{p}
"""


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*$", "", text, flags=re.M)


def read_sections(master: Path) -> list[Path]:
    """Follow \\include/\\input one level deep, in order."""
    seen: list[Path] = []
    for name in INCLUDE.findall(strip_comments(master.read_text(encoding="utf-8"))):
        p = master.parent / (name if name.endswith(".tex") else name + ".tex")
        if p.exists() and p not in seen:
            seen.append(p)
    return seen


def take_match(pattern: str, text: str) -> tuple[str | None, str]:
    m = re.search(pattern, text, re.S)
    if not m:
        return None, text
    return m.group(1).strip(), text[: m.start()] + "\n" + text[m.end() :]


def bracket_command(name: str, text: str) -> tuple[list[tuple[str, str]], str]:
    """Extract \\name[opt]{arg} occurrences (with or without the optional arg)."""
    out = []
    # one level of nested braces is allowed: \author[1]{Name \orcidlink{0000-...}}
    pattern = re.compile(
        r"\\" + name + r"(\[[^\]]*\])?\s*\{((?:[^{}]|\{[^{}]*\})*)\}"
    )
    for m in pattern.finditer(text):
        opt = (m.group(1) or "[]").strip("[]")
        out.append((opt, m.group(2).strip()))
    # also \\name{...} with a single mandatory group already covered above
    return out, pattern.sub("", text)


def latex_to_text(s: str) -> str:
    """Reduce inline LaTeX to plain text for metadata fields (YAML -> pandoc)."""
    s = re.sub(r"\\lipsum(?:\[[^\]]*\]|\{[^{}]*\})?", LOREM, s)
    s = re.sub(r"\\at\b", "@", s)
    s = re.sub(r"\\orcidlink\s*\{[^{}]*\}", "", s)   # author ORCID badges
    keep = r"(?:textbf|textit|emph|texttt|textrm|textsf|textsc|url|mbox|text|mathrm)"
    for _ in range(3):
        s = re.sub(r"\\" + keep + r"\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:cite[pt]?|ref|cref|label)(?:\[[^\]]*\])?\{([^{}]*)\}",
               r"[\1]", s)
    s = re.sub(r"\\\\\s*", " ", s)
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = re.sub(r"[{}]", "", s)
    s = re.sub(r"~", " ", s)
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = re.sub(r"\s*@\s*", "@", s)
    return re.sub(r"\s+", " ", s).strip()


def yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_front_matter(first: str) -> tuple[str, str]:
    meta: list[str] = []

    title, first = take_match(r"\\title\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", first)
    authors, first = bracket_command("author", first)
    affils, first = bracket_command("affil", first)

    lead, first = take_match(r"\\leadauthor\{([^{}]*)\}", first)
    short, first = take_match(r"\\shorttitle\{([^{}]*)\}", first)

    abstract, first = take_match(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", first)
    keywords, first = take_match(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", first)
    corr, first = take_match(r"\\begin\{corrauthor\}(.*?)\\end\{corrauthor\}", first)

    if title:
        meta.append(f"title: {yaml_str(latex_to_text(title))}")
    if lead:
        meta.append(f"lead-author: {yaml_str(latex_to_text(lead))}")
    if short:
        meta.append(f"running-title: {yaml_str(latex_to_text(short))}")
    if authors:
        # pandoc's template interpolates author entries as plain strings, so
        # keep each author one string: "Name (Affiliation)"
        affil_map = {k: v for k, v in affils if k}
        meta.append("author:")
        for opt, name in authors:
            name = latex_to_text(re.sub(r"\s+", " ", name))
            ids = [x.strip() for x in opt.split(",") if x.strip()]
            notes = [affil_map[i] for i in ids if i in affil_map]
            if notes:
                name = name + " (" + latex_to_text("; ".join(notes)) + ")"
            meta.append(f"  - {yaml_str(name)}")
    if corr:
        meta.append(f"correspondence: {yaml_str(latex_to_text(corr))}")
    if abstract:
        meta.append(f"abstract: {yaml_str(latex_to_text(abstract))}")
    if keywords:
        kw = [latex_to_text(k.strip()) for k in re.split(r"[|,]", keywords) if k.strip()]
        meta.append("keywords:")
        meta.extend(f"  - {yaml_str(k)}" for k in kw)

    return "---\n" + "\n".join(meta) + "\n---\n", first


REF_WORD = {
    "figure": "Figure",
    "table": "Table",
    "equation": "Equation",
    "section": "Section",
    "subsection": "Subsection",
    "subsubsection": "Subsubsection",
    "suppfigure": "Supplementary Figure",
    "supptable": "Supplementary Table",
    "videosupp": "Supplementary Video",
    "page": "p.",
}


def _brace_groups(text: str, i: int = 0) -> tuple[list[str], int]:
    """Read consecutive {..} groups starting at i, honouring nesting."""
    groups: list[str] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n or text[i] != "{":
            break
        depth, start, j = 0, i + 1, i
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        groups.append(text[start:j])
        i = j + 1
    return groups, i


def read_labels(directory: Path) -> dict[str, tuple[str, str]]:
    r"""label -> (number, counter) from the LaTeX .aux files of the PDF build.

    pandoc cannot number \ref/\cref, but LaTeX already did. Format:
    \newlabel{key}{{num}{page}{caption}{counter.num}{}} -- the caption field can
    itself contain braces, so parse brace-aware instead of by regex.
    """
    needle = r"\newlabel"
    labels: dict[str, tuple[str, str]] = {}
    for aux in sorted(directory.glob("*.aux")):
        try:
            text = aux.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        pos = 0
        while True:
            pos = text.find(needle, pos)
            if pos < 0:
                break
            pos += len(needle)
            groups = _brace_groups(text, pos)[0]
            if len(groups) < 2:
                continue
            key, payload = groups[0].strip(), groups[1]
            if not key or key.endswith("@cref"):
                continue
            parts = _brace_groups(payload)[0]
            if len(parts) < 4:
                continue
            num, anchor = parts[0].strip(), parts[3].strip()
            counter = anchor.split(".")[0] if anchor else ""
            if not num or counter in ("Doc-Start", "page", ""):
                continue
            labels.setdefault(key, (num, counter))
    return labels


def resolve_refs(body: str, labels: dict[str, tuple[str, str]]) -> str:
    r"""Replace \ref/\cref/\eqref with the numbers LaTeX already assigned."""
    bs = chr(92)

    def substitute(command: str, text: str, fn) -> str:
        needle = bs + command + "{"
        out, i = [], 0
        while True:
            j = text.find(needle, i)
            if j < 0:
                out.append(text[i:])
                break
            k = text.find("}", j + len(needle))
            if k < 0:
                out.append(text[i:])
                break
            key = text[j + len(needle) : k].strip()
            out.append(text[i:j])
            out.append(fn(key))
            i = k + 1
        return "".join(out)

    def num(key: str) -> str:
        return labels[key][0] if key in labels else "[" + key + "]"

    def typed(key: str) -> str:
        if key not in labels:
            return "[" + key + "]"
        val, counter = labels[key]
        word = REF_WORD.get(counter, counter.capitalize() if counter else "")
        return (word + " " + val).strip()

    def parenthesised(key: str) -> str:
        return "(" + num(key) + ")"

    body = substitute("eqref", body, parenthesised)
    body = substitute("cref", body, typed)
    body = substitute("Cref", body, typed)
    body = substitute("ref", body, num)
    return body


def strip_brace_macro(text: str, name: str) -> str:
    """Remove \\name{...} including its balanced braces."""
    out, i = [], 0
    token = "\\" + name + "{"
    while True:
        j = text.find(token, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k, depth = j + len(token), 1
        while k < len(text) and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        out.append(text[j + len(token) : k - 1])  # keep the contents only
        i = k
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("-o", "--out", default="build/flat.tex")
    args = ap.parse_args()

    master = Path(args.master).resolve()
    sections = read_sections(master)
    if not sections:
        print(f"no \\include found in {master}", file=sys.stderr)
        return 1

    bodies, first = [], True
    front = ""
    for path in sections:
        text = strip_comments(path.read_text(encoding="utf-8"))
        if first:
            front, text = build_front_matter(text)
            first = False
        bodies.append(text.strip())

    body = "\n\n".join(bodies)
    body = strip_brace_macro(body, "narrowfit")            # unwrap scaled tables
    body = re.sub(r"\\lipsum(?:\[[^\]]*\]|\{[^{}]*\})?", LOREM + "\n\n", body)
    body = PLUMBING.sub("", body)                          # PDF-only plumbing
    # supplementary files end with their own \section*{References}; citeproc
    # emits the one list of references
    body = re.sub(r"\\section\*?\{References\}", "", body)
    labels = read_labels(master.parent)
    if not labels:
        print(
            "note: no LaTeX .aux files found, so cross-references stay as [label]. "
            "Run `python build.py pdf` first to let LaTeX number them.",
            file=sys.stderr,
        )
    body = resolve_refs(body, labels)
    body = re.sub(r"\\vspace\*?\{[^}]*\}", "", body)
    body = re.sub(r"[ \t]+$", "", body, flags=re.M)
    body = re.sub(r"\n{3,}", "\n\n", body)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "%% generated by tools/tex2html.py -- do not edit\n"
        + SHIM
        + "\n\\begin{document}\n"
        + body
        + "\n\\end{document}\n",
        encoding="utf-8",
    )
    Path(str(out) + ".front.yaml").write_text(front, encoding="utf-8")
    print(f"sections: {', '.join(p.name for p in sections)}")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
