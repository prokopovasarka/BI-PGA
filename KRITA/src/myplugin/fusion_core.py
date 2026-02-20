import os
import tempfile
from dataclasses import dataclass

from krita import InfoObject
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPainter, QColor, QPixmap
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsBlurEffect
)


@dataclass
class Params:
    x: int = 0
    y: int = 0
    low_sigma: float = 8.0
    high_sigma: float = 2.0
    high_weight: float = 0.5
    base_is_low: bool = True # switch between frequencies


def gaussian_blur(img: QImage, radius: float) -> QImage:
    """
    Gaussian blur func
    """
    if radius <= 0:
        return img

    pix = QPixmap.fromImage(img) # for Qt Graphics effects

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pix)

    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    item.setGraphicsEffect(blur)

    scene.addItem(item)

    out = QImage(
        pix.size(),
        QImage.Format_RGBA8888
    )
    out.fill(Qt.transparent)

    painter = QPainter(out)
    scene.render(painter)
    painter.end()

    return out


def high_pass(img: QImage, sigma: float) -> QImage:
    blurred = gaussian_blur(img, sigma)

    a = img.convertToFormat(QImage.Format_RGBA8888)
    b = blurred.convertToFormat(QImage.Format_RGBA8888)

    out = QImage(a.size(), QImage.Format_RGBA8888)

    for y in range(a.height()):
        for x in range(a.width()):
            ca = a.pixelColor(x, y)
            cb = b.pixelColor(x, y)

            r = ca.red()   - cb.red()   + 128
            g = ca.green() - cb.green() + 128
            b = ca.blue()  - cb.blue()  + 128

            out.setPixelColor(
                x, y,
                QColor(
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                    255
                )
            )

    return out


def to_luminance(img: QImage) -> QImage:
    """
    Convert image to perceptual grayscale
    """
    src = img.convertToFormat(QImage.Format_RGBA8888)
    out = QImage(src.size(), QImage.Format_RGBA8888)

    for y in range(src.height()):
        for x in range(src.width()):
            c = src.pixelColor(x, y)
            y_ = int(
                0.2126 * c.red() +
                0.7152 * c.green() +
                0.0722 * c.blue()
            )
            out.setPixelColor(x, y, QColor(y_, y_, y_, 255))

    return out


def load_canvas_projection_as_qimage(doc) -> QImage:
    """
    Robust preview source: export projection to temp PNG via Krita, load as QImage.
    Works regardless of document color model/depth for preview.
    """
    if doc is None:
        raise RuntimeError("No active document (open an image first).")

    fd, path = tempfile.mkstemp(prefix="krita_fuse_", suffix=".png")
    os.close(fd)

    try:
        info = InfoObject()
        ok = doc.exportImage(path, info)
        if not ok:
            raise RuntimeError("Krita failed to export canvas for preview.")

        img = QImage(path)
        if img.isNull():
            raise RuntimeError("Failed to load exported canvas preview.")
        return img
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def fuse(base: QImage, second: QImage, p: Params) -> QImage:
    """
    Fusion of two pictures for hyprid picture making
    """
    if base.isNull() or second.isNull():
        return QImage()

    base = base.convertToFormat(QImage.Format_RGBA8888)
    second = second.convertToFormat(QImage.Format_RGBA8888)

    if p.base_is_low:
        low_img = base
        high_img = second
    else:
        low_img = second
        high_img = base

    low_gray = to_luminance(low_img)
    low = gaussian_blur(low_gray, p.low_sigma)

    high = high_pass(high_img, p.high_sigma)

    out = QImage(low.size(), QImage.Format_RGBA8888)
    out.fill(Qt.black)

    painter = QPainter(out)
    painter.drawImage(0, 0, low)
    painter.setOpacity(p.high_weight)
    painter.drawImage(p.x, p.y, high)
    painter.end()

    return out


def put_result_on_new_layer(doc, result: QImage, layer_name="Fused Result"):
    """
    Write result pixels into a new paint layer.
    Kept strict to avoid corrupt output: only RGBA/U8 documents.
    """
    if doc is None:
        raise RuntimeError("No active document.")
    if result is None or result.isNull():
        raise RuntimeError("Nothing to put on canvas (result is empty).")

    if doc.colorModel() != "RGBA" or doc.colorDepth() != "U8":
        raise RuntimeError(
            f"Cannot write pixels to this document format ({doc.colorModel()} / {doc.colorDepth()}). "
            "Convert the document to RGBA 8-bit."
        )

    w, h = doc.width(), doc.height()
    img = result.convertToFormat(QImage.Format_RGBA8888)
    if img.width() != w or img.height() != h:
        raise RuntimeError("Result size does not match canvas size.")

    root = doc.rootNode()
    layer = doc.createNode(layer_name, "paintlayer")
    root.addChildNode(layer, None)

    ptr = img.bits()
    ptr.setsize(w * h * 4)
    layer.setPixelData(bytes(ptr), 0, 0, w, h)

    doc.refreshProjection()
    doc.setActiveNode(layer)
