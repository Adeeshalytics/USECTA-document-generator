"""Convert supplied artwork to a multi-resolution Windows icon, unchanged."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    with Image.open(ROOT / "assets" / "usecta-icon.png") as source:
        artwork = source.convert("RGBA")
        edge = max(artwork.size)
        square = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
        square.alpha_composite(artwork, ((edge - artwork.width) // 2, (edge - artwork.height) // 2))
        square.save(ROOT / "assets" / "usecta-icon.ico", format="ICO",
                    sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    print("Windows icon prepared with seven resolutions; original PNG retained.")


if __name__ == "__main__":
    main()
