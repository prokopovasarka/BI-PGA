from krita import Extension
from PyQt5.QtWidgets import QApplication
from .fusion_dialog import FusionDialog


class ImageFusionExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self._dlg = None

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "krita_hybrid_image_open",
            "Hybrid Image Plugin",
            "tools/scripts",
        )
        action.triggered.connect(lambda checked=False, w=window: self._open(w))

    def _open(self, window):
        """
        Setup plugin
        
        :param self: Description
        :param window: Description
        """
        if self._dlg is not None:
            try:
                self._dlg.show()
                self._dlg.raise_()
                self._dlg.activateWindow()
                return
            except RuntimeError:
                self._dlg = None

        parent = None
        if window is not None:
            try:
                parent = window.qwindow()
            except RuntimeError:
                parent = None
        if parent is None:
            parent = QApplication.activeWindow()

        dlg = FusionDialog(parent)
        self._dlg = dlg
        dlg.destroyed.connect(lambda *_: setattr(self, "_dlg", None))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
