from krita import Krita
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QSpinBox, QSlider, QCheckBox
)

from .fusion_core import (
    Params,
    load_canvas_projection_as_qimage,
    fuse,
    put_result_on_new_layer
)


class FusionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hybrid Image")
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.p = Params()
        self.base = QImage()
        self.second = QImage()
        self.result = QImage()

        self._ui()
        self._wire()

        self.use_current_canvas()
        self._update_labels()


    def _ui(self):
        """
        Whole ui logic, init all buttons, spins etc.
        setting range and values
        """
        self.msg = QLabel("")
        self.msg.setWordWrap(True)

        self.preview = QLabel("Preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(520, 320)
        self.preview.setStyleSheet("border: 1px solid #444;")

        self.btn_canvas = QPushButton("Use current canvas (LOW)")
        self.btn_pick = QPushButton("Choose second image (HIGH)")
        self.chk_base_low = QCheckBox("Canvas = LOW frequency image")
        self.chk_base_low.setChecked(True)
        self.btn_reset = QPushButton("Reset settings")

        self.spin_x = QSpinBox()
        self.spin_x.setRange(-5000, 5000)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(-5000, 5000)

        self.low_sigma = QSlider(Qt.Horizontal)
        self.low_sigma.setRange(1, 20)
        self.low_sigma.setValue(8)

        self.high_sigma = QSlider(Qt.Horizontal)
        self.high_sigma.setRange(1, 10)
        self.high_sigma.setValue(2)

        self.high_weight = QSlider(Qt.Horizontal)
        self.high_weight.setRange(0, 100)
        self.high_weight.setValue(50)

        self.btn_put = QPushButton("Put result on new layer")
        self.btn_save = QPushButton("Save result")
        self.btn_close = QPushButton("Close")

        root = QVBoxLayout(self)
        root.addWidget(self.msg)
        root.addWidget(self.preview, 1)

        r1 = QHBoxLayout()
        r1.addWidget(self.btn_canvas)
        r1.addWidget(self.btn_pick)
        r1.addWidget(self.btn_reset)
        root.addLayout(r1)
        root.addWidget(self.chk_base_low)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("X:"))
        r2.addWidget(self.spin_x)
        r2.addWidget(QLabel("Y:"))
        r2.addWidget(self.spin_y)
        root.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Low blur"))
        r3.addWidget(self.low_sigma)
        r3.addWidget(QLabel("High blur"))
        r3.addWidget(self.high_sigma)
        r3.addWidget(QLabel("High weight"))
        r3.addWidget(self.high_weight)
        root.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(self.btn_put)
        r4.addWidget(self.btn_save)
        r4.addStretch(1)
        r4.addWidget(self.btn_close)
        root.addLayout(r4)


    def _wire(self):
        """
        Connecting events to buttons, checkbox and spin
        """
        self.btn_close.clicked.connect(self.close)
        self.btn_canvas.clicked.connect(self.use_current_canvas)
        self.btn_pick.clicked.connect(self.choose_second_image)
        self.btn_reset.clicked.connect(self.reset)
        self.chk_base_low.toggled.connect(self._changed)
        self.chk_base_low.toggled.connect(self._update_labels)

        for w in (
            self.spin_x, self.spin_y,
            self.low_sigma, self.high_sigma, self.high_weight
        ):
            w.valueChanged.connect(self._changed)

        self.btn_put.clicked.connect(self.put_on_canvas)
        self.btn_save.clicked.connect(self.save_result)


    def _update_labels(self):
        """
        Changing label on buttons
        """
        if self.chk_base_low.isChecked():
            self.btn_canvas.setText("Use current canvas (LOW)")
            self.btn_pick.setText("Choose second image (HIGH)")
        else:
            self.btn_canvas.setText("Use current canvas (HIGH)")
            self.btn_pick.setText("Choose second image (LOW)")


    def _set_msg(self, text="", error=False):
        self.msg.setText(("⚠️ " if error else "") + text)

    def reset(self):
        """
        Reset settings to default values
        """
        self.spin_x.setValue(0)
        self.spin_y.setValue(0)
        self.low_sigma.setValue(8)
        self.high_sigma.setValue(2)
        self.high_weight.setValue(50)

    def use_current_canvas(self):
        try:
            doc = Krita.instance().activeDocument()
            if doc is None:
                raise RuntimeError("Open an image first.")

            self.base = load_canvas_projection_as_qimage(doc)
            self._set_msg("Canvas loaded as LOW frequency image.")
            self._rebuild()
        except Exception as e:
            self._set_msg(str(e), True)

    def choose_second_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select HIGH frequency image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"
        )
        if not path:
            return

        img = QImage(path)
        if img.isNull():
            self._set_msg("Unsupported image.", True)
            return

        self.second = img
        self._set_msg("Second image loaded.")
        self._rebuild()

    def _changed(self):
        """
        Handling changes for pictures
        """
        self.p.x = self.spin_x.value()
        self.p.y = self.spin_y.value()
        self.p.low_sigma = self.low_sigma.value()
        self.p.high_sigma = self.high_sigma.value()
        self.p.high_weight = self.high_weight.value() / 100.0
        self.p.base_is_low = self.chk_base_low.isChecked()
        self._rebuild()

    def _rebuild(self):
        if self.base.isNull() or self.second.isNull():
            self.preview.setText("Load both images.")
            return

        self.result = fuse(self.base, self.second, self.p)
        self._update_preview()

    def _update_preview(self):
        if self.result.isNull():
            return

        pix = QPixmap.fromImage(self.result)
        self.preview.setPixmap(
            pix.scaled(
                self.preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_preview()

    def put_on_canvas(self):
        try:
            doc = Krita.instance().activeDocument()
            put_result_on_new_layer(doc, self.result)
            self._set_msg("Hybrid image added as new layer.")
        except Exception as e:
            self._set_msg(str(e), True)

    def save_result(self):
        if self.result.isNull():
            self._set_msg("Nothing to save.", True)
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save hybrid image",
            "",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;WEBP (*.webp)"
        )
        if not path:
            return

        if self.result.save(path):
            self._set_msg("Saved.")
        else:
            self._set_msg("Save failed.", True)
