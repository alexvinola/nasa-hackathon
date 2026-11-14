"""Draws a fake blood-pressure monitor display for the vision test."""
import sys
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (640, 420), (40, 44, 52))
d = ImageDraw.Draw(img)
d.rounded_rectangle((60, 40, 580, 380), radius=30, fill=(170, 190, 160), outline=(20, 20, 20), width=6)
def font(size):
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()
small, big = font(28), font(110)
d.text((90, 70), "SYS mmHg", fill=(20, 20, 20), font=small)
d.text((300, 50), "138", fill=(20, 20, 20), font=big)
d.text((90, 185), "DIA mmHg", fill=(20, 20, 20), font=small)
d.text((300, 165), "91", fill=(20, 20, 20), font=big)
d.text((90, 300), "PULSE /min", fill=(20, 20, 20), font=small)
d.text((330, 290), "77", fill=(20, 20, 20), font=font(70))
img.save(sys.argv[1])
