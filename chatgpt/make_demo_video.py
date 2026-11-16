"""Assemble the numcheck demo video (docs/demo.mp4) from saved ChatGPT screenshots. Needs pillow, imageio, imageio-ffmpeg."""
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

R = Path("/Users/France/.claude/projects/-Users-France-Downloads/3c482dd3-5db9-4894-b892-1c9bb31179f0/tool-results")
OUT = Path(sys.argv[1])
W, H, FPS = 1456, 814, 15
TEAL, BG = (15, 110, 110), (14, 16, 18)
FONT = "/System/Library/Fonts/Helvetica.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def shot(name, caption):
    im = Image.open(R / f"mcp-claude-in-chrome-blob-{name}.jpg").convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(im.resize((W, int(im.height * W / im.width))), (0, 0))
    d = ImageDraw.Draw(canvas, "RGBA")
    f = font(26, True)
    tw = d.textlength(caption, font=f)
    x, y = (W - tw) / 2, H - 120
    d.rounded_rectangle((x - 22, y - 14, x + tw + 22, y + 42), 14, fill=(15, 110, 110, 235))
    d.text((x, y), caption, font=f, fill="white")
    return canvas


def card(title, sub=""):
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    ft, fs = font(64, True), font(30)
    d.text(((W - d.textlength(title, font=ft)) / 2, H / 2 - 70), title, font=ft, fill="white")
    for i, line in enumerate(sub.split("\n") if sub else []):
        d.text(((W - d.textlength(line, font=fs)) / 2, H / 2 + 20 + i * 44), line, font=fs, fill=(170, 220, 215))
    d.rectangle((W / 2 - 60, H / 2 - 100, W / 2 + 60, H / 2 - 94), fill=TEAL)
    return c


SCENES = [
    (card("numcheck for ChatGPT", "Finds numbers in clinical trial reports that cannot be right,\nwithout the data. Open source."), 4),
    (card("1 · Pasted text", "Tool: check_text"), 2.5),
    (shot("1794820561358-6cx36q", "Pick numcheck with @numcheck"), 3),
    (shot("1794820561358-kx4dj8", "Paste a results paragraph"), 3.5),
    (shot("1794820561358-3qusbs", "40 people cannot be 89.1 % of any group: flagged"), 6),
    (card("2 · PubMed Central article", "Tool: check_pmc"), 2.5),
    (shot("1794820609259-qmehwu", "Give a PMCID"), 3),
    (shot("1794820614032-0pjye0", "24 numbers checked, none flagged"), 5.5),
    (card("3 · Document by URL", "Tool: check_url (made-up demo report)"), 2.5),
    (shot("1794820667507-qlfokr", "Link a PDF, XML or text document"), 3),
    (shot("1794820677937-arhjzo", "14 numbers checked, 9 flagged, by check"), 5.5),
    (shot("1794820677937-4yy6w9", "Each flag: printed vs computed"), 6),
    (shot("1794820677937-523m4h", "Tests, CIs and table totals too"), 5.5),
    (card("4 · What it checks", "Tool: list_checks"), 2.5),
    (shot("1794820716127-nbv2z6", "Eleven checks, explained"), 4.5),
    (shot("1794820716127-5fp8t8", "Verdicts explained, e.g. truncated vs rounded"), 4.5),
    (card("A flag is not a verdict", "It means: cannot be reproduced from the other numbers.\ngithub.com/joonalorenz-commits/numcheck"), 5),
]


def main():
    frames = [(np.asarray(img), sec) for img, sec in SCENES]
    fade = int(0.4 * FPS)
    w = imageio.get_writer(OUT, fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=2)
    for i, (arr, sec) in enumerate(frames):
        for _ in range(int(sec * FPS) - fade):
            w.append_data(arr)
        if i + 1 < len(frames):
            nxt = frames[i + 1][0]
            for k in range(fade):
                a = (k + 1) / (fade + 1)
                w.append_data((arr * (1 - a) + nxt * a).astype(np.uint8))
        else:
            for _ in range(fade):
                w.append_data(arr)
    w.close()
    print(OUT, sum(s for _, s in SCENES), "s")


if __name__ == "__main__":
    main()
