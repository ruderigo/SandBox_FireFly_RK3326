"""Formatted messages, rendered for a small screen.

LXMF's FIELD_RENDERER says how a message's text is written: plain (0),
Micron (1, NomadNet's markup), Markdown (2, what NomadNet sends and Sideband
reads) or BBCode (3). FireFly turns them into lines with a style each:

  "h1" / "h2"  heading           "li"     list item (bullet or number kept)
  "quote"      quoted text       "code"   code (monospace)
  "rule"       a divider         "text"   ordinary text

Inline markup (bold, italic, underline, strike, code spans, colours) is
dropped and the words kept; links become "text (url)". Nothing is executed
and nothing is fetched: it's text in, text out.
"""
import re

PLAIN, MICRON, MARKDOWN, BBCODE = 0, 1, 2, 3

_MD_LINK = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_MD_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
_MD_INLINE = [
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"\*\*\*(.+?)\*\*\*"), r"\1"),
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"__(.+?)__"), r"\1"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"\1"),
    (re.compile(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])"), r"\1"),
    (re.compile(r"~~(.+?)~~"), r"\1"),
]


def _md_inline(s):
    s = _MD_LINK.sub(lambda m: m.group(1) if m.group(1) == m.group(2) or not m.group(1)
                     else f"{m.group(1)} ({m.group(2)})", s)
    s = _MD_AUTOLINK.sub(r"\1", s)
    for rx, rep in _MD_INLINE:
        s = rx.sub(rep, s)
    return s.replace("\\*", "*").replace("\\_", "_").replace("\\#", "#")


def markdown(text):
    out, in_code = [], False
    for raw in text.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append(("code", line))
            continue
        st = line.strip()
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", st)
        if m:
            out.append(("h1" if len(m.group(1)) == 1 else "h2", _md_inline(m.group(2))))
        elif re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", st):
            out.append(("rule", ""))
        elif st.startswith(">"):
            out.append(("quote", _md_inline(st.lstrip(">").strip())))
        elif re.match(r"^[-*+]\s+\[[ xX]\]\s+", st):
            done = st[st.index("[") + 1].lower() == "x"
            out.append(("li", ("☑ " if done else "☐ ") + _md_inline(st.split("]", 1)[1].strip())))
        elif re.match(r"^[-*+]\s+", st):
            indent = (len(line) - len(line.lstrip())) // 2
            out.append(("li", "  " * indent + "• " + _md_inline(st[2:].strip())))
        elif re.match(r"^\d+[.)]\s+", st):
            out.append(("li", _md_inline(st)))
        elif "|" in st and re.match(r"^\|?\s*:?-{2,}", st):
            continue                                   # a table's header rule
        elif st.startswith("|") and st.endswith("|"):
            out.append(("text", "  ".join(c.strip() for c in _md_inline(st).strip("|").split("|"))))
        else:
            out.append(("text", _md_inline(st)))
    return out


# Micron (NomadNet): ` starts a tag. `! bold, `* italic, `_ underline, `F<rgb>/`f colour,
# `B<rgb>/`b background, `c `l `r `a alignment, `` reset, `[label`url] link, `<…> field.
_MI_LINK = re.compile(r"`\[([^`\]]*)`([^\]]*)\]")
_MI_FIELD = re.compile(r"`<[^>]*>")
_MI_COLOR = re.compile(r"`[FB][0-9a-fA-F]{3}|`[FB]T[0-9a-fA-F]{6}")
_MI_TAG = re.compile(r"``|`[!*_fbclra=]")


def _mi_inline(s):
    s = _MI_LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(1) else m.group(2), s)
    s = _MI_FIELD.sub("", s)
    s = _MI_COLOR.sub("", s)
    return _MI_TAG.sub("", s)


def micron(text):
    out, literal = [], False
    for raw in text.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if line.strip() == "`=":
            literal = not literal
            continue
        if literal:
            out.append(("code", line))
            continue
        if line.startswith("#"):
            continue                                   # a Micron comment
        if line.startswith(">"):
            depth = len(line) - len(line.lstrip(">"))
            out.append(("h1" if depth == 1 else "h2", _mi_inline(line.lstrip(">").strip())))
        elif line.startswith("-") and len(set(line.strip())) <= 2 and len(line.strip()) <= 2:
            out.append(("rule", ""))                   # "-" or "-∿": a divider
        else:
            out.append(("text", _mi_inline(line)))
    return out


_BB = re.compile(r"\[/?(?:b|i|u|s|code|quote|color|size|url|img)(?:=[^\]]*)?\]", re.I)


def bbcode(text):
    text = re.sub(r"\[url=([^\]]+)\]([^\[]*)\[/url\]", r"\2 (\1)", text, flags=re.I)
    return [("text", _BB.sub("", ln.rstrip())) for ln in text.replace("\r", "").split("\n")]


def render(text, renderer):
    """-> [(style, text)]; plain text (or an unknown renderer) comes back as it was."""
    try:
        if renderer == MARKDOWN:
            return markdown(text)
        if renderer == MICRON:
            return micron(text)
        if renderer == BBCODE:
            return bbcode(text)
    except Exception:
        pass
    return [("text", ln) for ln in text.split("\n")]
