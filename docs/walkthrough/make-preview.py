"""Write the original README preview SVG and optional conceptual animation frames.

Pure standard library; no network. Rasterising frames to PNG/GIF is a separate,
documented step (see README.md in this folder). Frames are conceptual artwork,
not a browser recording.
"""
import argparse
from pathlib import Path

W, H = 1280, 640
C = {"carbon": "#05060A", "pearl": "#F2EFE8", "gold": "#C7A968", "blue": "#5E8FA8", "emerald": "#0E3B2E",
     "ink2": "#C9CBD1", "ink3": "#9A9DA6", "line": "#2A2D35", "amber": "#D29B4A"}
FONT = "'DM Sans', Inter, 'Segoe UI', system-ui, -apple-system, Roboto, Arial, sans-serif"
STAGES = [
    ("Edit", "Exact cut + hashes", "M4 20l4-1 11-11-3-3L5 16z M14 6l3 3"),
    ("Approve", "Scoped owner approval", "M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z M8.5 12l2.5 2.5 4.5-5"),
    ("Schedule", "One saved job, read back", "M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4 M12 13v3l2 1.5"),
    ("Verify post", "Native post observed", "M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"),
    ("Comments", "Triage; reply unsent", "M4 5h12v8H9l-4 3v-3H4z M16 9h4v8h-1v3l-3-3h-5v-2"),
    ("Follower check", "Approved gate kept", "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M15 11l2 2 4-4"),
    ("Guide delivery", "Receipt, not trigger", "M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h4"),
]
LOCK = "M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3"
HOLD = "M8 3h8l5 5v8l-5 5H8l-5-5V8z M9 12h6"
DETAIL = [
    "Finish the asset and caption; review claims, captions and rights.",
    "The owner approves the exact asset, caption, account, time and action.",
    "One configured scheduler, one saved job, read back before relying on it.",
    "Open the actual post. A scheduler success badge is not proof.",
    "Sort requests from discussion. Example reply: “Please check your DMs for the next step.” (unsent)",
    "Keep the approved follower gate and recheck loop. Unknown is not eligible.",
    "A fired trigger or accepted send is not delivery. Bind the receipt to the recipient.",
]


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(active=None, held=None, caption=None):
    """active: highlighted stage index; held: gate index for an exception frame."""
    left, right, y = 110, W - 110, 330
    step = (right - left) / 6
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">',
           '<title id="t">Content Operations release walkthrough (simulation)</title>',
           '<desc id="d">Original conceptual preview of seven stages: edit, approve, schedule, verify the post, comment triage, follower check and guide delivery. Exceptions hold the flow at their gate. Synthetic; nothing is sent.</desc>',
           '<defs><radialGradient id="g1" cx=".9" cy="0" r=".7"><stop offset="0" stop-color="#C7A968" stop-opacity=".16"/><stop offset="1" stop-color="#C7A968" stop-opacity="0"/></radialGradient>',
           '<radialGradient id="g2" cx="0" cy="1" r=".8"><stop offset="0" stop-color="#0E3B2E" stop-opacity=".75"/><stop offset="1" stop-color="#0E3B2E" stop-opacity="0"/></radialGradient>',
           f'<linearGradient id="fill" x1="0" x2="1"><stop offset="0" stop-color="{C["blue"]}"/><stop offset="1" stop-color="{C["gold"] if held is None else C["amber"]}"/></linearGradient></defs>',
           f'<rect width="{W}" height="{H}" fill="{C["carbon"]}"/><rect width="{W}" height="{H}" fill="url(#g1)"/><rect width="{W}" height="{H}" fill="url(#g2)"/>',
           f'<g font-family="{FONT}">',
           f'<text x="64" y="74" fill="{C["gold"]}" font-size="15" font-weight="600" letter-spacing="3">CONTENT OPERATIONS · RELEASE WALKTHROUGH</text>',
           f'<text x="64" y="134" fill="{C["pearl"]}" font-size="50" font-weight="600" letter-spacing="-1.5">From final cut to <tspan fill="{C["gold"]}">verified delivery.</tspan></text>',
           f'<text x="64" y="176" fill="{C["ink2"]}" font-size="19">Seven handoffs. Each needs its own evidence. An unresolved gate stops the journey.</text>']
    # simulation badge
    out.append(f'<g transform="translate({W - 64 - 276},50)"><rect width="276" height="36" rx="18" fill="#C7A968" fill-opacity=".1" stroke="{C["gold"]}" stroke-opacity=".6"/>'
               f'<circle cx="20" cy="18" r="4" fill="{C["gold"]}"/><text x="34" y="23.5" fill="{C["gold"]}" font-size="13" font-weight="600" letter-spacing="1.6">SIMULATION · SYNTHETIC</text></g>')
    # track
    limit = 6 if held is None else held
    reach = 6 if active is None else min(active, limit)
    out.append(f'<rect x="{left}" y="{y - 1.5}" width="{right - left}" height="3" rx="1.5" fill="{C["line"]}"/>')
    out.append(f'<rect x="{left}" y="{y - 1.5}" width="{step * reach:.1f}" height="3" rx="1.5" fill="url(#fill)"/>')
    for i, (name, note, path) in enumerate(STAGES):
        cx = left + step * i
        locked = held is not None and i > held
        is_held = held is not None and i == held
        current = (active == i) or (active is None and i == 6 and held is None)
        if current and is_held:
            disc, stroke, ink, icon = C["amber"], C["amber"], C["carbon"], HOLD
        elif current:
            disc, stroke, ink, icon = C["gold"], C["gold"], C["carbon"], path
        elif locked:
            disc, stroke, ink, icon = "#0C0E13", "#4A4D56", "#5D6069", LOCK
        elif active is None or i < (active or 0):
            disc, stroke, ink, icon = "#0C0E13", C["blue"], "#A9C6D6", path
        else:
            disc, stroke, ink, icon = "#0C0E13", "#3A3D46", C["ink3"], path
        dash = ' stroke-dasharray="4 4"' if locked else ''
        if current:
            out.append(f'<circle cx="{cx:.1f}" cy="{y}" r="44" fill="{disc}" fill-opacity=".14"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{y}" r="32" fill="{disc}" stroke="{stroke}" stroke-width="2"{dash}/>')
        out.append(f'<g transform="translate({cx - 14:.1f},{y - 14}) scale(1.1667)" fill="none" stroke="{ink}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="{icon}"/></g>')
        label_fill = C["pearl"] if current else ("#6D7079" if locked else C["ink2"])
        out.append(f'<text x="{cx:.1f}" y="{y + 62}" text-anchor="middle" fill="{C["ink3"]}" font-size="12" letter-spacing="2">{i + 1:02d}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y + 86}" text-anchor="middle" fill="{label_fill}" font-size="17" font-weight="600">{esc(name)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y + 108}" text-anchor="middle" fill="{"#5D6069" if locked else C["ink3"]}" font-size="13">{esc("Locked" if locked else note)}</text>')
    # caption panel
    if caption is None:
        caption = "Exceptions hold the flow: missing approval · duplicate response · follower status unknown · sensitive comment"
    tone = C["amber"] if held is not None else C["gold"]
    out.append(f'<rect x="64" y="486" width="{W - 128}" height="58" rx="12" fill="#0B0D12" stroke="{C["line"]}"/>')
    out.append(f'<rect x="64" y="486" width="4" height="58" rx="2" fill="{tone}"/>')
    out.append(f'<text x="88" y="521" fill="{C["ink2"]}" font-size="16">{esc(caption)}</text>')
    out.append(f'<text x="64" y="594" fill="{C["ink3"]}" font-size="14">Instructions, templates and offline evidence checks. Not a scheduler, posting service or ManyChat replacement. Nothing here is sent.</text>')
    out.append('</g></svg>\n')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frames", type=Path, help="Optional NEW directory for conceptual animation frame SVGs")
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    (here / "workflow-preview.svg").write_text(svg(), encoding="utf-8", newline="\n")
    if args.frames:
        args.frames.mkdir(parents=False, exist_ok=False)
        for i in range(7):
            (args.frames / f"frame-{i}.svg").write_text(svg(active=i, caption=f"{i + 1:02d} · {DETAIL[i]}"), encoding="utf-8", newline="\n")
        (args.frames / "frame-7.svg").write_text(svg(active=1, held=1, caption="Exception: approval missing. The flow holds at stage 02; later stages stay locked."), encoding="utf-8", newline="\n")
    print("preview written")


if __name__ == "__main__":
    main()
