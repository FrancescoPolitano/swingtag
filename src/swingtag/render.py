"""The page of an item and the error page, as HTML strings (FR-30..FR-35).

Pure: model and theme in, HTML out. No JavaScript, one inline style block, one
request to reach the menu. Every value from names, links or the theme is escaped.
"""

from __future__ import annotations

from html import escape

from .catalog import Button, Item
from .i18n import format_date
from .theme import Colors, Theme

# 24x24 stroke icons, one per kind.
_ICONS = {
    "document": '<path d="M6 2h9l5 5v15H6zM14 2v6h6"/>',
    "image": '<path d="M3 4h18v16H3zM3 16l5-5 5 5 3-3 5 5"/><circle cx="16" cy="8" r="2"/>',
    "audio": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "video": '<path d="M3 5h13v14H3zM16 10l5-3v10l-5-3"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
}

# Secondary tones derive only from --t, --bg and --p (spec/ASSUMPTIONS.md T-14).
_CSS = """*{box-sizing:border-box}
:root{%(vars)s;--muted:color-mix(in srgb,var(--t) 62%%,var(--bg));
--line:color-mix(in srgb,var(--t) 14%%,var(--bg));--card:color-mix(in srgb,var(--t) 5%%,var(--bg))}
%(dark)shtml{-webkit-text-size-adjust:100%%}body{margin:0;background:var(--bg);color:var(--t);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:44rem;margin:0 auto;padding:1rem 1rem 3rem;overflow-wrap:anywhere}
.notice{background:color-mix(in srgb,var(--p) 12%%,var(--bg));border:1px solid var(--line);
border-radius:.5rem;padding:.6rem .8rem;font-size:.85rem;margin-bottom:1rem}
header{padding:.5rem 0 1.25rem;border-bottom:1px solid var(--line);margin-bottom:1.25rem}
.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;color:var(--muted);margin-bottom:.75rem}
.brand img{height:40px;width:auto}h1{font-size:1.6rem;line-height:1.25;margin:0 0 .35rem}
.sub{color:var(--muted);margin:0}ul{list-style:none;margin:0;padding:0}li{margin-bottom:.75rem}
a.b{display:flex;align-items:center;gap:.75rem;min-height:56px;padding:.85rem 1rem;background:var(--card);
border:1px solid var(--line);border-radius:.6rem;text-decoration:none;color:var(--t);font-weight:600}
a.b:focus-visible{outline:3px solid var(--p);outline-offset:2px}
svg{flex:none;width:24px;height:24px;fill:none;stroke:var(--p);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.l{flex:1;min-width:0}.c{display:block;color:var(--muted);font-weight:400;font-size:.8rem;margin-top:.15rem}
.empty{background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:1.25rem;color:var(--muted)}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
footer p{margin:0 0 .25rem}"""


def _vars(colors: Colors) -> str:
    return f"--p:{colors.primary};--bg:{colors.background};--t:{colors.text}"


def _style(theme: Theme) -> str:
    dark = ""
    if theme.colors_dark is not None:
        dark = "@media (prefers-color-scheme:dark){:root{%s}}\n" % _vars(theme.colors_dark)
    return _CSS % {"vars": _vars(theme.colors), "dark": dark}


def _head(title: str, theme: Theme) -> str:
    return (
        f"<!doctype html><html lang={escape(theme.locale)}><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<meta name=robots content=noindex,nofollow>"
        f"<title>{escape(title)}</title><style>{_style(theme)}</style>"
    )


def _header(theme: Theme, collection: str) -> str:
    logo = f'<img src="/_assets/{escape(theme.logo)}" alt="">' if theme.logo else ""
    return f"<div class=brand>{logo}{escape(theme.header or collection)}</div>"


def _button(button: Button, theme: Theme) -> str:
    rel = ' rel="noopener noreferrer"' if button.kind == "link" else ""
    context = f"<span class=c>{escape(button.context)}</span>" if button.context else ""
    name = escape(theme.string(f"kind_{button.kind}"))
    return (
        f'<li><a class=b href="{escape(button.href)}"{rel}>'
        f'<svg viewBox="0 0 24 24" role=img aria-label="{name}">{_ICONS[button.kind]}</svg>'
        f"<span class=l>{escape(button.label)}{context}</span></a></li>"
    )


def render_page(item: Item, theme: Theme) -> str:
    heading = item.label or item.collection
    brand = theme.header or item.collection
    parts = [_head(f"{heading} · {brand}", theme), "<body><div class=wrap>"]
    if theme.notice:
        parts.append(f"<div class=notice>{escape(theme.notice)}</div>")
    parts.append(f"<header>{_header(theme, item.collection)}<h1>{escape(heading)}</h1>")
    if theme.header:
        parts.append(f"<p class=sub>{escape(item.collection)}</p>")
    parts.append("</header>")
    if item.buttons:
        parts.append("<ul>" + "".join(_button(b, theme) for b in item.buttons) + "</ul>")
    else:
        parts.append(f"<div class=empty>{escape(theme.string('empty'))}</div>")
    footer = []
    if theme.footer:
        footer.append(f"<p>{escape(theme.footer)}</p>")
    if item.updated_at is not None:
        stamp = format_date(item.updated_at, theme.locale, theme.timezone)
        footer.append(f"<p>{escape(theme.string('updated'))} {escape(stamp)}</p>")
    if footer:
        parts.append("<footer>" + "".join(footer) + "</footer>")
    parts.append("</div></body></html>")
    return "".join(parts)


def render_not_found(theme: Theme) -> str:
    """Page for any unknown path. Reveals nothing about which tokens exist."""
    title = theme.string("not_found_title")
    return "".join([
        _head(title, theme),
        "<body><div class=wrap>",
        f"<div class=notice>{escape(theme.notice)}</div>" if theme.notice else "",
        f"<header>{_header(theme, '')}<h1>{escape(title)}</h1></header>",
        f"<div class=empty>{escape(theme.string('not_found_body'))}</div>",
        "</div></body></html>",
    ])
