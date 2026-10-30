"""
Generates high-resolution application icons for orang3D.
Creates:
- resources/icons/orang3d.png (256x256 PNG)
- resources/icons/orang3d.ico (Multi-resolution Windows ICO: 16, 32, 48, 64, 128, 256)
"""

import os
from PIL import Image, ImageDraw

def create_orang3d_icon():
    os.makedirs("resources/icons", exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded background plate (#1a1d24 dark engineering surface)
    margin = 12
    draw.rounded_rectangle(
        [(margin, margin), (size - margin, size - margin)],
        radius=48,
        fill="#1a1d24",
        outline="#ff6b35",
        width=6,
    )

    # Retaining Wall Cantilever Profile in Vibrant Orange (#ff6b35)
    # Wall Stem: x: 90..130, y: 50..180
    # Footing Base: x: 50..206, y: 180..216
    # Toe: 50..90, Heel: 130..206
    wall_points = [
        (100, 50),   # Stem top-left
        (125, 50),   # Stem top-right
        (135, 180),  # Stem base-right / heel junction
        (206, 180),  # Heel right-top
        (206, 216),  # Heel right-bottom
        (50, 216),   # Toe left-bottom
        (50, 180),   # Toe left-top
        (90, 180),   # Toe right-top / stem base-left
    ]
    draw.polygon(wall_points, fill="#ff6b35", outline="#ff8354", width=3)

    # Shear Key under footing: x: 120..150, y: 216..236
    key_points = [
        (115, 216),
        (145, 216),
        (140, 236),
        (120, 236),
    ]
    draw.polygon(key_points, fill="#e8590c", outline="#ff8354", width=2)

    # 3D Backfill Soil Strata Lines (Cyan/Blue #00a6fb)
    draw.line([(135, 90), (195, 75)], fill="#00a6fb", width=3)
    draw.line([(135, 130), (200, 115)], fill="#00a6fb", width=3)
    draw.line([(135, 170), (205, 155)], fill="#06d6a0", width=3)  # Groundwater line

    # Save PNG
    png_path = "resources/icons/orang3d.png"
    img.save(png_path, "PNG")
    print(f"Generated {png_path}")

    # Save Multi-resolution Windows ICO
    ico_path = "resources/icons/orang3d.ico"
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"Generated {ico_path}")

if __name__ == "__main__":
    create_orang3d_icon()
