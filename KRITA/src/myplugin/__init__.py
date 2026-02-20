from krita import Krita
from .extension import ImageFusionExtension

Krita.instance().addExtension(ImageFusionExtension(Krita.instance()))
