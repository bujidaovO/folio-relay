"""Render the single editable SVG into application and interface icons."""
from io import BytesIO
from pathlib import Path

from PIL import Image
import resvg_py


def main():
    root = Path(__file__).resolve().parent
    svg = root / 'app.svg'
    png = resvg_py.svg_to_bytes(svg_path=str(svg), width=1024, height=1024,
                              skip_system_fonts=True)
    icon = Image.open(BytesIO(png)).convert('RGBA')
    icon.save(root / 'app.png', optimize=True)
    icon.save(root / 'app.icns')
    icon.save(root / 'app.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    # Generated interface resource; edit app.svg rather than this copy.
    (root.parent / 'dist' / 'brand.svg').write_bytes(svg.read_bytes())


if __name__ == '__main__':
    main()
