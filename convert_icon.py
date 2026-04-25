#!/usr/bin/env python3
"""Convert icon.png to icon.ico"""

from PIL import Image
import os

icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
ico_path = os.path.join(os.path.dirname(__file__), 'icon.ico')

# Open the PNG and convert to ICO
img = Image.open(icon_path)

# Resize to a square if needed (ICO format typically uses square dimensions)
if img.size[0] != img.size[1]:
    size = max(img.size[0], img.size[1])
    new_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    offset = ((size - img.size[0]) // 2, (size - img.size[1]) // 2)
    new_img.paste(img, offset, img if img.mode == 'RGBA' else None)
    img = new_img

# Convert to ICO format with multiple sizes for better quality
img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

print(f"✓ Converted {icon_path} to {ico_path}")
