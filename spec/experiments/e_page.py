"""Experiment on the page assumptions (T-14, T-15): a worst-case prototype page.

Builds out/page.html with ten buttons (two of each kind, long labels with
context), five inline SVG icons, a notice, a logo, a footer, theme colours with
color-mix() derived tones and a dark block, then measures its size.
The markup approximates the product page; it is not the product renderer.
"""
import os
from html import escape

ICONS = {  # 24x24 single-path icons, stroke only
    "document": '<path d="M6 2h9l5 5v15H6zM14 2v6h6"/>',
    "image": '<path d="M3 4h18v16H3zM3 16l5-5 5 5 3-3 5 5"/><circle cx="16" cy="8" r="2"/>',
    "audio": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "video": '<path d="M3 5h13v14H3zM16 10l5-3v10l-5-3"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
}
STYLE = """*{box-sizing:border-box}
:root{--p:#8a2d1c;--bg:#fbf7f2;--t:#1f1b16;--muted:color-mix(in srgb,var(--t) 62%,var(--bg));
--line:color-mix(in srgb,var(--t) 14%,var(--bg));--card:color-mix(in srgb,var(--t) 5%,var(--bg))}
@media (prefers-color-scheme:dark){:root{--p:#e0a15a;--bg:#171412;--t:#f2ede6}}
html{-webkit-text-size-adjust:100%}body{margin:0;background:var(--bg);color:var(--t);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:44rem;margin:0 auto;padding:1rem 1rem 3rem}
.notice{background:color-mix(in srgb,var(--p) 12%,var(--bg));border:1px solid var(--line);border-radius:.5rem;padding:.6rem .8rem;font-size:.85rem;margin-bottom:1rem}
header{padding:.5rem 0 1.25rem;border-bottom:1px solid var(--line);margin-bottom:1.25rem}
.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;color:var(--muted);margin-bottom:.75rem}
.brand img{height:40px;width:auto}h1{font-size:1.6rem;line-height:1.25;margin:0 0 .35rem;word-break:break-word}
.sub{color:var(--muted);margin:0}ul{list-style:none;margin:0;padding:0}li{margin-bottom:.75rem}
a.b{display:flex;align-items:center;gap:.75rem;min-height:56px;padding:.85rem 1rem;background:var(--card);
border:1px solid var(--line);border-radius:.6rem;text-decoration:none;color:var(--t);font-weight:600}
a.b:focus-visible{outline:3px solid var(--p);outline-offset:2px}
svg{flex:none;width:24px;height:24px;fill:none;stroke:var(--p);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.l{flex:1;min-width:0}.c{display:block;color:var(--muted);font-weight:400;font-size:.8rem;margin-top:.15rem}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}"""


def button(kind, label, context, href, external=False):
    rel = ' rel="noopener noreferrer"' if external else ""
    ctx = f"<span class=c>{escape(context)}</span>" if context else ""
    return (f'<li><a class=b href="{escape(href)}"{rel}><svg viewBox="0 0 24 24" role=img aria-label="{kind}">'
            f"{ICONS[kind]}</svg><span class=l>{escape(label)}{ctx}</span></a></li>")


def build():
    kinds = ["document", "image", "audio", "video", "link"] * 2
    items = []
    for i, k in enumerate(kinds):
        href = "https://example.com/book-a-table-for-tonight" if k == "link" else f"/3xk9m2p7qhv4/entry-number-{i}/a-fairly-long-file-name-{i}.{ {'document':'pdf','image':'jpg','audio':'m4a','video':'mp4'}[k] }"
        items.append(button(k, f"Instructions for pruning and seasonal care, part {i}", "Care and maintenance", href, k == "link"))
    return ("<!doctype html><html lang=it><meta charset=utf-8>"
            '<meta name=viewport content="width=device-width,initial-scale=1">'
            "<meta name=robots content=noindex,nofollow><title>Olivo Leccino - Vivaio Radici Lente</title>"
            f"<style>{STYLE}</style><body><div class=wrap><div class=notice>Demo environment: fictional content.</div>"
            '<header><div class=brand><img src="/_assets/logo.svg" alt="">Vivaio Radici Lente</div>'
            "<h1>Olivo Leccino</h1><p class=sub>Vivaio Radici Lente</p></header>"
            f"<ul>{''.join(items)}</ul><footer>Via dei Campi 12, open every day 8-19<br>Aggiornato il 25/09/2026 14:30</footer>"
            "</div></body></html>")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(os.path.join(out, "_assets"), exist_ok=True)
    html = build()
    open(os.path.join(out, "page.html"), "w").write(html)
    open(os.path.join(out, "_assets", "logo.svg"), "w").write(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><path d="M20 4c10 8 10 24 0 32C10 28 10 12 20 4z" fill="#3d6b4f"/></svg>')
    size = len(html.encode())
    print(f"{'PASS' if size < 15360 else 'FAIL'} T-15: worst-case page with 10 buttons = {size} bytes (limit 15360)")
