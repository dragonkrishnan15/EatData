"""Capture current feature screenshots and compose a high-resolution collage.

Outputs:
- d:/EatDataAnylst/images/01_data_table_diff.png
- d:/EatDataAnylst/images/02_quality_profile.png
- d:/EatDataAnylst/images/03_visualizations.png
- d:/EatDataAnylst/images/04_ai_assistant.png
- d:/EatDataAnylst/images/05_domain_templates.png
- d:/EatDataAnylst/images/eatdata_features_collage.png
"""

import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGES_DIR = Path(r"d:\EatDataAnylst\images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
if not EDGE_EXE.exists():
    EDGE_EXE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def capture_view(url: str, output_png: Path):
    if output_png.exists():
        output_png.unlink()
    cmd = [
        str(EDGE_EXE),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1280,800",
        f"--screenshot={output_png}",
        url,
    ]
    print(f"Capturing: {output_png.name} from {url}...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    if output_png.exists():
        print(f" -> {output_png.name}: {output_png.stat().st_size} bytes")
    else:
        print(f" -> WARNING: {output_png.name} was not created!")
    time.sleep(0.5)


def get_font(size: int, bold: bool = False):
    font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
    font_path = Path("C:/Windows/Fonts") / font_name
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def build_collage():
    screenshots = [
        (
            "1. Interactive Data Grid: Search, Sort, Pagination & Prospective Cell Diffs",
            IMAGES_DIR / "01_data_table_diff.png",
        ),
        (
            "2. Column-Level Statistical Quality Profiler & Type Confidence",
            IMAGES_DIR / "02_quality_profile.png",
        ),
        (
            "3. Missingness & Categorical Distribution Visualizations",
            IMAGES_DIR / "03_visualizations.png",
        ),
        (
            "4. Privacy-Guarded Optional AI Assistant: SHA-256 Payload & Recipes",
            IMAGES_DIR / "04_ai_assistant.png",
        ),
        (
            "5. Curated Industry Domain Cleaning Templates Catalog",
            IMAGES_DIR / "05_domain_templates.png",
        ),
    ]

    thumb_w = 960
    thumb_h = 600
    margin = 24
    header_h = 100
    banner_h = 38
    cols = 2
    rows = 3

    total_w = (cols * thumb_w) + ((cols + 1) * margin)
    total_h = header_h + (rows * (thumb_h + banner_h)) + ((rows + 1) * margin)

    collage = Image.new("RGB", (total_w, total_h), color=(15, 20, 28))
    draw = ImageDraw.Draw(collage)

    title_font = get_font(28, bold=True)
    sub_font = get_font(14, bold=False)
    banner_font = get_font(13, bold=True)
    card_title_font = get_font(20, bold=True)
    card_body_font = get_font(13, bold=False)

    # Header
    draw.text((margin, 24), "EatData Offline Workbench", fill=(241, 245, 249), font=title_font)
    draw.text(
        (margin, 60),
        "Universal Data Preparation & Analysis Platform — 100% Local Engine & Privacy Guaranteed",
        fill=(148, 163, 184),
        font=sub_font,
    )

    # Badge in header
    badge_text = "LOCAL ENGINE 127.0.0.1  •  ZERO RAW ROWS TRANSMITTED"
    badge_x = total_w - margin - 480
    draw.rounded_rectangle(
        [badge_x, 32, total_w - margin, 68],
        radius=6,
        fill=(22, 29, 39),
        outline=(16, 185, 129),
        width=1,
    )
    draw.text((badge_x + 18, 42), badge_text, fill=(16, 185, 129), font=banner_font)

    # Draw items
    for idx in range(6):
        r = idx // cols
        c = idx % cols

        x = margin + c * (thumb_w + margin)
        y = header_h + margin + r * (thumb_h + banner_h + margin)

        if idx < len(screenshots):
            caption, img_path = screenshots[idx]
            # Banner
            draw.rounded_rectangle(
                [x, y, x + thumb_w, y + banner_h],
                radius=4,
                fill=(22, 29, 39),
                outline=(43, 56, 76),
                width=1,
            )
            draw.text((x + 14, y + 10), caption, fill=(241, 245, 249), font=banner_font)

            # Screenshot Image
            if img_path.exists():
                try:
                    img = Image.open(img_path)
                    img_resized = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    collage.paste(img_resized, (x, y + banner_h))
                    draw.rectangle(
                        [x, y + banner_h, x + thumb_w, y + banner_h + thumb_h],
                        outline=(43, 56, 76),
                        width=1,
                    )
                except Exception as err:
                    print(f"Error loading {img_path}: {err}")
        else:
            # Slot 6: Architectural Summary Card
            card_top = y
            draw.rounded_rectangle(
                [x, card_top, x + thumb_w, card_top + banner_h + thumb_h],
                radius=6,
                fill=(22, 29, 39),
                outline=(59, 130, 246),
                width=2,
            )

            # Title
            draw.text(
                (x + 36, card_top + 36),
                "Universal Architecture & Privacy Invariants",
                fill=(96, 165, 250),
                font=card_title_font,
            )

            bullets = [
                (
                    "Local-First Loopback Engine:",
                    "Strictly binds to 127.0.0.1 loopback interface. 100% offline processing.",
                ),
                (
                    "Universal Format Ingestion:",
                    "Safe CSV/TSV, JSON/NDJSON, and zero-dependency Excel (.xlsx) importing.",
                ),
                (
                    "Interactive Table & Diff Engine:",
                    "Click-to-sort headers, real-time query filtering, pagination "
                    "(25/50/100/All), and cell diffs.",
                ),
                (
                    "Deterministic Replay & Undo/Redo:",
                    "Immutable raw baseline ensures mathematical precision. "
                    "Full Ctrl+Z/Ctrl+Y history.",
                ),
                (
                    "Statistical Quality Profiler:",
                    "Calculates type confidence, null percentages, distinct counts, "
                    "min/max, mean, patterns.",
                ),
                (
                    "Optional AI Assistant with Consent Gate:",
                    "Zero raw rows transmitted. Previews SHA-256 payload and "
                    "validates recipes locally.",
                ),
                (
                    "SQLite Persistence & Domain Templates:",
                    "Saves versioned pipelines to local SQLite (~/.eatdata/workbench.db). "
                    "Ready-to-use recipes.",
                ),
            ]

            curr_y = card_top + 84
            for title, desc in bullets:
                draw.text((x + 36, curr_y), f"• {title}", fill=(241, 245, 249), font=banner_font)
                draw.text((x + 54, curr_y + 24), desc, fill=(148, 163, 184), font=card_body_font)
                curr_y += 68

    output_collage = IMAGES_DIR / "eatdata_features_collage.png"
    collage.save(output_collage, quality=95)
    print(f"Collage successfully saved: {output_collage}")


def main():
    port = 8765
    features = [
        ("01_data_table_diff", f"http://127.0.0.1:{port}/?demo=1&diff=1&tab=dataTab"),
        ("02_quality_profile", f"http://127.0.0.1:{port}/?demo=1&tab=profileTab"),
        ("03_visualizations", f"http://127.0.0.1:{port}/?demo=1&tab=visualizeTab"),
        ("04_ai_assistant", f"http://127.0.0.1:{port}/?demo=1&ai_demo=1&tab=aiTab"),
        ("05_domain_templates", f"http://127.0.0.1:{port}/?demo=1&tab=templatesTab"),
    ]

    for name, url in features:
        out_png = IMAGES_DIR / f"{name}.png"
        capture_view(url, out_png)

    build_collage()


if __name__ == "__main__":
    main()
