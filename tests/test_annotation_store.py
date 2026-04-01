import sys

from PySide6.QtWidgets import QApplication

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation
from alchemyannotate.services.annotation_store import AnnotationStore

# QApplication needed for signals
_app = QApplication.instance() or QApplication(sys.argv)


def test_store_get_or_create():
    store = AnnotationStore()
    ann = store.get_or_create("test.jpg", 640, 480)
    assert ann.image_filename == "test.jpg"
    assert ann.image_width == 640
    assert ann.image_height == 480
    assert len(ann.boxes) == 0

    # Second call returns same object
    ann2 = store.get_or_create("test.jpg")
    assert ann2 is ann


def test_store_dirty_tracking():
    store = AnnotationStore()
    ann = ImageAnnotation(image_filename="a.jpg", image_width=100, image_height=100)
    store.set("a.jpg", ann)
    assert "a.jpg" in store.dirty_files()

    store.mark_clean("a.jpg")
    assert "a.jpg" not in store.dirty_files()


def test_store_has_annotations():
    store = AnnotationStore()
    ann = ImageAnnotation(
        image_filename="a.jpg",
        boxes=[BoundingBox(class_name="x", xmin=0, ymin=0, xmax=10, ymax=10)],
    )
    store.set("a.jpg", ann)
    assert store.has_annotations("a.jpg") is True
    assert store.has_annotations("b.jpg") is False


def test_store_clear():
    store = AnnotationStore()
    store.set("a.jpg", ImageAnnotation(image_filename="a.jpg"))
    store.clear()
    assert store.get("a.jpg") is None
    assert len(store.dirty_files()) == 0


def test_store_signal_emitted():
    store = AnnotationStore()
    received = []
    store.annotation_changed.connect(lambda f: received.append(f))
    store.set("img.jpg", ImageAnnotation(image_filename="img.jpg"))
    assert received == ["img.jpg"]

    store.mark_dirty("img.jpg")
    assert received == ["img.jpg", "img.jpg"]
