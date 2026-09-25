#!/usr/bin/env python3
"""Scope design-reference/ichivol-workspace/style.css under .<scope>-page."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "design-reference/ichivol-workspace/style.css"

SKIP = re.compile(
    r"^(aside|nav|header|footer|body|html|#sidebar|#menu|#crumb|#kill|#toast|"
    r"\.brand|\.brandmark|\.nav-label|\.side-bottom|\.shell|\.breadcrumb|"
    r"\.header-right|\.engine|\.pill|\.kill|\.avatar|\.header-settings|"
    r"\.settings-link|main|button|a|input|select|textarea|\*)\b"
)


def split_top(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        if text.startswith("/*", i):
            j = text.find("*/", i)
            i = n if j < 0 else j + 2
            continue
        if text.startswith("@media", i):
            b = text.find("{", i)
            depth = 0
            j = b
            while j < n:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            out.append(("media", text[i:j]))
            i = j
            continue
        if text.startswith("@", i):
            if "{" in text[i : i + 80]:
                b = text.find("{", i)
                depth = 0
                j = b
                while j < n:
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
                i = j
            else:
                j = text.find(";", i)
                i = n if j < 0 else j + 1
            continue
        b = text.find("{", i)
        if b < 0:
            break
        depth = 0
        j = b
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        out.append(("rule", text[i:j]))
        i = j
    return out


def scope_sel(sel: str, scope: str) -> str | None:
    sel = sel.strip()
    if not sel or sel == ":root":
        return None
    parts: list[str] = []
    for p in sel.split(","):
        p = p.strip()
        if not p or p == ":root" or SKIP.search(p):
            continue
        parts.append(p if p.startswith(scope) else f"{scope} {p}")
    return ", ".join(parts) or None


def fmt(sel: str, body: str) -> str:
    props = [p.strip() for p in body.split(";") if p.strip()]
    return sel + " {\n" + "\n".join(f"  {p};" for p in props) + "\n}"


def do_rule(rt: str, scope: str) -> str | None:
    m = re.match(r"^([^{]+)\{(.*)\}$", rt.strip(), re.S)
    if not m:
        return None
    sel, body = m.group(1).strip(), m.group(2)
    if sel == ":root":
        return None
    scoped = scope_sel(sel, scope)
    return fmt(scoped, body) if scoped else None


def do_media(mt: str, scope: str) -> str | None:
    m = re.match(r"^(@media[^{]+)\{(.*)\}$", mt.strip(), re.S)
    if not m:
        return None
    head, inner = m.group(1), m.group(2)
    rules: list[str] = []
    i, n = 0, len(inner)
    while i < n:
        while i < n and inner[i].isspace():
            i += 1
        if i >= n:
            break
        b = inner.find("{", i)
        if b < 0:
            break
        depth = 0
        j = b
        while j < n:
            if inner[j] == "{":
                depth += 1
            elif inner[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        r = do_rule(inner[i:j], scope)
        if r:
            rules.append(r)
        i = j
    return f"{head} {{\n" + "\n".join(rules) + "\n}" if rules else None


def generate(scope_name: str) -> str:
    scope = f".{scope_name}-page"
    raw = SRC.read_text()
    css = re.sub(r"@import\s+url\([^)]+\)\s*;", "", raw, count=1)
    out: list[str] = [
        f"/** {scope_name} — CSS maquette scopé {scope} */\n",
        f"""{scope} {{
  --bg: #faf8f5;
  --card: #fefdfb;
  --line: #ddd9d3;
  --ink: #202b36;
  --muted: #7d8288;
  --blue: #1a7df5;
  --green: #0b8f83;
  --red: #c8412f;
  --amber: #a76c17;
  color: var(--ink);
  font: 14px Manrope, Arial, sans-serif;
  padding: 0;
  max-width: 1800px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}}
{scope} *,
{scope} *::before,
{scope} *::after {{ box-sizing: border-box; }}
{scope} button {{
  cursor: pointer;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  padding: 10px 14px;
  color: inherit;
  transition: .18s;
  font: inherit;
}}
{scope} button:hover {{ border-color: #a4b9d1; background: #f1f5fa; }}
{scope} a {{ color: inherit; text-decoration: none; }}
{scope} input,
{scope} select,
{scope} textarea {{
  font: inherit;
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 7px;
  padding: 10px 12px;
  color: var(--ink);
  max-width: 100%;
}}
""",
    ]
    for kind, text in split_top(css):
        r = do_rule(text, scope) if kind == "rule" else do_media(text, scope)
        if r:
            out.append(r)
    out.append(
        f"""
.dash-shell {scope} .page-head h1,
.dash-shell.is-mobile {scope} .page-head h1,
{scope} .page-head h1 {{
  font: 38px Newsreader, Georgia, serif;
  margin: 0 0 6px;
  letter-spacing: -1px;
}}
.dash-shell.is-mobile {scope} .page-head .subtitle,
.dash-shell.is-mobile {scope} .page-head p,
{scope} .subtitle {{
  font-size: 12px !important;
  line-height: 1.7;
  color: var(--muted);
  margin: 0;
}}
{scope} table {{ font-size: 14px; }}
{scope} tr.clickable {{ font-size: 14px; }}
{scope} td {{ font-size: 14px; }}
{scope} .table-wrap {{ overflow: auto; padding: 0; }}
@media (max-width: 800px) {{
  .dash-shell {scope} .page-head h1,
  .dash-shell.is-mobile {scope} .page-head h1,
  {scope} .page-head h1 {{ font-size: 32px; }}
  {scope} .page-head {{
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 18px;
  }}
}}
"""
    )
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: gen-maquette-page-css.py <scope> <out.css>")
        sys.exit(2)
    scope_name, outp = sys.argv[1], Path(sys.argv[2])
    outp.write_text(generate(scope_name))
    print("wrote", outp, outp.stat().st_size)
