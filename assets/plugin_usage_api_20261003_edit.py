"""Add '& Claude Code' under the 'Claude Desktop' label of the homepage figure; all other pixels unchanged."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

src = Path(sys.argv[1])
out = Path(sys.argv[2])
im = Image.open(src).convert("RGB")
px = im.load()

# Bounding box of the existing "Claude Desktop" label (dark pixels in the label row).
xs, ys = [], []
for x in range(340, 515):
    for y in range(424, 460):
        r, g, b = px[x, y]
        if r + g + b < 250:
            xs.append(x)
            ys.append(y)
left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
centre = (left + right) / 2
label_h = bottom - top

# Match the label's dark navy: average of its darkest quarter of pixels.
colour = (24, 34, 72)  # perceived navy of the anti-aliased original label

font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", size=int(label_h * 0.92))
text = "& Claude Code"
draw = ImageDraw.Draw(im)
w = draw.textlength(text, font=font)
y = bottom + 6
draw.text((centre - w / 2, y), text, font=font, fill=colour)
bbox = draw.textbbox((centre - w / 2, y), text, font=font)
assert bbox[3] < 495, f"new line would reach the illustration below: {bbox}"
im.save(out, optimize=True)
print("label box", (left, top, right, bottom), "colour", colour, "new text box", bbox)
