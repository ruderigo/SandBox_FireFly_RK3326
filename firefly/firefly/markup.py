"""Formatted messages, rendered for a small screen.

LXMF's FIELD_RENDERER says how a message's text is written: plain (0),
Micron (1, NomadNet's markup), Markdown (2, what NomadNet sends and Sideband
reads) or BBCode (3). FireFly turns them into lines, each with a block style
and a list of inline spans:

  block styles  "h1" "h2" heading, "li" list item, "quote", "code" (a code
                block), "rule" (a divider), "text"
  span flags    "b" bold, "i" italic, "u" underline, "s" strikethrough,
                "code" inline code, "link" a link's text (its address follows
                in brackets)

render(text, renderer) -> [(block_style, [(frozenset(flags), text), ...])]

Nothing is executed and nothing is fetched: it's text in, styled text out.
"""
import re

PLAIN, MICRON, MARKDOWN, BBCODE = 0, 1, 2, 3
NONE = frozenset()


def plain(spans):
    """The words of a line, without styling."""
    return "".join(t for _, t in spans)


def _merge(spans):
    out = []
    for fl, t in spans:
        if not t:
            continue
        if out and out[-1][0] == fl:
            out[-1] = (fl, out[-1][1] + t)
        else:
            out.append((fl, t))
    return out


# ------------------------------------------------------------------ Markdown
_MD_TOKEN = re.compile(
    r"(?P<code>`+)(?P<code_t>.+?)(?P=code)"
    r"|!?\[(?P<link_t>[^\]]*)\]\((?P<link_u>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|<(?P<auto>https?://[^>\s]+)>"
    r"|\*\*\*(?P<bi1>.+?)\*\*\*|___(?P<bi2>.+?)___"
    r"|\*\*(?P<b1>.+?)\*\*|__(?P<b2>.+?)__"
    r"|(?<![\w*])\*(?![\s*])(?P<i1>.+?)(?<![\s*])\*(?![\w*])"
    r"|(?<![\w_])_(?![\s_])(?P<i2>.+?)(?<![\s_])_(?![\w_])"
    r"|~~(?P<s>.+?)~~"
    r"|\\(?P<esc>[\\`*_{}\[\]()#+\-.!~|>])")


def md_spans(s, flags=NONE):
    out, pos = [], 0
    for m in _MD_TOKEN.finditer(s):
        if m.start() > pos:
            out.append((flags, s[pos:m.start()]))
        g = m.groupdict()
        if g["code_t"] is not None:
            out.append((flags | {"code"}, g["code_t"].strip() if g["code_t"].strip() else g["code_t"]))
        elif g["link_u"] is not None:
            label, url = g["link_t"], g["link_u"]
            if label and label != url:
                out += md_spans(label, flags | {"link"})
                out.append((flags, f" ({url})"))
            else:
                out.append((flags | {"link"}, url))
        elif g["auto"] is not None:
            out.append((flags | {"link"}, g["auto"]))
        elif g["bi1"] is not None or g["bi2"] is not None:
            out += md_spans(g["bi1"] or g["bi2"], flags | {"b", "i"})
        elif g["b1"] is not None or g["b2"] is not None:
            out += md_spans(g["b1"] or g["b2"], flags | {"b"})
        elif g["i1"] is not None or g["i2"] is not None:
            out += md_spans(g["i1"] or g["i2"], flags | {"i"})
        elif g["s"] is not None:
            out += md_spans(g["s"], flags | {"s"})
        elif g["esc"] is not None:
            out.append((flags, g["esc"]))
        pos = m.end()
    if pos < len(s):
        out.append((flags, s[pos:]))
    return _merge(out)


def markdown(text):
    out, in_code = [], False
    for raw in text.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append(("code", [(frozenset({"code"}), line)]))
            continue
        st = line.strip()
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", st)
        if m:
            out.append(("h1" if len(m.group(1)) == 1 else "h2", md_spans(m.group(2), frozenset({"b"}))))
        elif re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", st):
            out.append(("rule", []))
        elif st.startswith(">"):
            out.append(("quote", md_spans(st.lstrip(">").strip())))
        elif re.match(r"^[-*+]\s+\[[ xX]\]\s+", st):
            done = st[st.index("[") + 1].lower() == "x"
            out.append(("li", [(NONE, "☑ " if done else "☐ ")] + md_spans(st.split("]", 1)[1].strip())))
        elif re.match(r"^[-*+]\s+", st):
            indent = (len(line) - len(line.lstrip())) // 2
            out.append(("li", [(NONE, "  " * indent + "• ")] + md_spans(st[2:].strip())))
        elif re.match(r"^\d+[.)]\s+", st):
            n, rest = st.split(None, 1) if " " in st else (st, "")
            out.append(("li", [(NONE, n + " ")] + md_spans(rest)))
        elif "|" in st and re.match(r"^\|?\s*:?-{2,}", st):
            continue                                   # a table's header rule
        elif st.startswith("|") and st.endswith("|"):
            cells = [md_spans(c.strip()) for c in st.strip("|").split("|")]
            row = []
            for k, c in enumerate(cells):
                row += ([(NONE, "  ")] if k else []) + c
            out.append(("text", _merge(row)))
        else:
            out.append(("text", md_spans(st)))
    return out


# ------------------------------------------------------------------ Micron (NomadNet)
# ` starts a tag: `! bold, `* italic, `_ underline (toggles), `F<rgb>/`f colour,
# `B<rgb>/`b background, `c `l `r `a alignment, `` reset all, `[label`url] link, `<…> field.
_MI_TOKEN = re.compile(r"`\[(?P<lt>[^`\]]*)`(?P<lu>[^\]]*)\]|`<[^>]*>|`[FB](?:T[0-9a-fA-F]{6}|[0-9a-fA-F]{3})"
                       r"|(?P<reset>``)|`(?P<tag>[!*_fbclra])")


def mi_spans(s, state):
    """state: the set of flags open from earlier lines (Micron's toggles carry over)."""
    out, pos = [], 0
    for m in _MI_TOKEN.finditer(s):
        if m.start() > pos:
            out.append((frozenset(state), s[pos:m.start()]))
        if m.group("lu") is not None:
            label, url = m.group("lt"), m.group("lu")
            if label and label != url:
                out.append((frozenset(state | {"link"}), label))
                out.append((frozenset(state), f" ({url})"))
            else:
                out.append((frozenset(state | {"link"}), url))
        elif m.group("reset"):
            state.clear()
        elif m.group("tag"):
            flag = {"!": "b", "*": "i", "_": "u"}.get(m.group("tag"))
            if flag:
                state ^= {flag}
        pos = m.end()
    if pos < len(s):
        out.append((frozenset(state), s[pos:]))
    return _merge(out)


def micron(text):
    out, literal, state = [], False, set()
    for raw in text.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if line.strip() == "`=":
            literal = not literal
            continue
        if literal:
            out.append(("code", [(frozenset({"code"}), line)]))
            continue
        if line.startswith("#"):
            continue                                   # a Micron comment
        if line.startswith(">"):
            depth = len(line) - len(line.lstrip(">"))
            out.append(("h1" if depth == 1 else "h2", mi_spans(line.lstrip(">").strip(), state | {"b"})))
        elif line.startswith("-") and len(line.strip()) <= 2:
            out.append(("rule", []))                   # "-" or "-∿": a divider
        else:
            out.append(("text", mi_spans(line, state)))
    return out


# ------------------------------------------------------------------ BBCode
_BB_TOKEN = re.compile(r"\[url=(?P<u>[^\]]+)\](?P<ut>[^\[]*)\[/url\]|\[(?P<close>/?)(?P<tag>b|i|u|s|code|quote|color|size|url|img)(?:=[^\]]*)?\]", re.I)


def bbcode(text):
    out, state = [], set()
    for line in text.replace("\r", "").split("\n"):
        spans, pos = [], 0
        for m in _BB_TOKEN.finditer(line):
            if m.start() > pos:
                spans.append((frozenset(state), line[pos:m.start()]))
            if m.group("u"):
                spans.append((frozenset(state | {"link"}), m.group("ut") or m.group("u")))
                if m.group("ut") and m.group("ut") != m.group("u"):
                    spans.append((frozenset(state), f" ({m.group('u')})"))
            else:
                flag = {"b": "b", "i": "i", "u": "u", "s": "s", "code": "code"}.get(m.group("tag").lower())
                if flag:
                    (state.discard if m.group("close") else state.add)(flag)
            pos = m.end()
        if pos < len(line):
            spans.append((frozenset(state), line[pos:]))
        out.append(("text", _merge(spans)))
    return out


def render(text, renderer):
    """-> [(block_style, spans)]. Plain text (or an unknown renderer) comes back as it was."""
    try:
        if renderer == MARKDOWN:
            return markdown(text)
        if renderer == MICRON:
            return micron(text)
        if renderer == BBCODE:
            return bbcode(text)
    except Exception:
        pass
    return [("text", [(NONE, ln)]) for ln in text.split("\n")]
