# scripts/utils/thumbnail.py
"""
Generates a JPEG thumbnail from the first page of a PDF.
Renders directly at target size (no resize step, no blur).
Quality=100 (maximum). Reduces only if output exceeds Telegram's 200 KB limit.
"""

import os
import fitz
from PIL import Image

MAX_DIM   = 320
MAX_KB    = 190
QUALITIES = [100, 95, 90, 85, 80, 70, 60]


def generate_thumbnail(pdf_path: str, output_path: str) -> bool:
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            print("[THUMB] No pages."); doc.close(); return False
        page = doc[0]
        rect = page.rect
        zoom = min(MAX_DIM / rect.width, MAX_DIM / rect.height)
        pix  = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csRGB)
        doc.close()
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        print(f"[THUMB] Rendered: {img.width}×{img.height} px")
        for quality in QUALITIES:
            img.save(output_path, format="JPEG", quality=quality, optimize=False)
            size_kb = os.path.getsize(output_path) / 1024
            print(f"[THUMB] quality={quality} → {size_kb:.1f} KB")
            if size_kb <= MAX_KB:
                print(f"[THUMB] ✓ quality={quality}, {size_kb:.1f} KB")
                return True
        print("[THUMB] Warning: best-effort kept")
        return True
    except Exception as e:
        import traceback
        print(f"[THUMB] Failed: {e}\n{traceback.format_exc()}")
        return False
