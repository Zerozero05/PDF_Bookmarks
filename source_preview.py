"""Bounded, read-only crops in the same normalized display coordinates as OCR."""

import math
import pymupdf


def render_source_crop(pdf_path, pdf_page, rect, *, max_width=640, max_height=150):
    if (type(pdf_page) is not int or pdf_page < 1 or not isinstance(rect, (tuple, list))
            or len(rect) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in rect)
            or not 0 <= rect[0] < rect[2] <= 1 or not 0 <= rect[1] < rect[3] <= 1):
        raise ValueError("此项没有有效的原目录行位置；请手动查看目录页。")
    if any(type(v) is not int or not 1 <= v <= 2048 for v in (max_width, max_height)):
        raise ValueError("目录行预览尺寸无效。")
    with pymupdf.open(str(pdf_path)) as document:
        if not document.is_pdf or document.needs_pass or pdf_page > document.page_count:
            raise ValueError("无法读取原目录页。")
        page = document[pdf_page - 1]
        x0, y0, x1, y1 = rect
        pad_y = max(0.004, (y1 - y0) * 0.2)
        crop = pymupdf.Rect(max(0, x0 - .008) * page.rect.width,
                            max(0, y0 - pad_y) * page.rect.height,
                            min(1, x1 + .008) * page.rect.width,
                            min(1, y1 + pad_y) * page.rect.height)
        scale = min(3, (max_width - .5) / crop.width, (max_height - .5) / crop.height)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=crop,
                                 colorspace=pymupdf.csRGB, alpha=False)
        # A fractional clip origin rounds outwards at both edges. Bound the
        # final raster as well as the requested scale, including rotated pages.
        if pixmap.width > max_width or pixmap.height > max_height:
            ratio = min(max_width / pixmap.width, max_height / pixmap.height)
            pixmap = pymupdf.Pixmap(pixmap, max(1, int(pixmap.width * ratio)),
                                   max(1, int(pixmap.height * ratio)), None)
        return pixmap.tobytes("png")
