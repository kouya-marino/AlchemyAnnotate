import tempfile
from pathlib import Path

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation
from alchemyannotate.services.io_coco import CocoIO


def test_coco_write_read_roundtrip():
    annotations = {
        "img1.jpg": ImageAnnotation(
            image_filename="img1.jpg",
            image_width=640,
            image_height=480,
            boxes=[
                BoundingBox(class_name="cat", xmin=10, ymin=20, xmax=110, ymax=120),
            ],
        ),
        "img2.jpg": ImageAnnotation(
            image_filename="img2.jpg",
            image_width=800,
            image_height=600,
            boxes=[
                BoundingBox(class_name="dog", xmin=50, ymin=50, xmax=200, ymax=200),
                BoundingBox(class_name="cat", xmin=300, ymin=300, xmax=400, ymax=400),
            ],
        ),
    }
    class_list = ["cat", "dog"]

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "annotations.json"
        CocoIO.write_all(annotations, json_path, class_list)

        assert json_path.exists()

        restored_classes = list(class_list)
        restored = CocoIO.read_all(json_path, restored_classes)

        assert "img1.jpg" in restored
        assert "img2.jpg" in restored
        assert len(restored["img1.jpg"].boxes) == 1
        assert len(restored["img2.jpg"].boxes) == 2
        assert restored["img1.jpg"].boxes[0].class_name == "cat"
        assert restored["img1.jpg"].image_width == 640

        # Check COCO bbox conversion (x, y, w, h) -> (xmin, ymin, xmax, ymax)
        box = restored["img1.jpg"].boxes[0]
        assert abs(box.xmin - 10) < 1
        assert abs(box.ymin - 20) < 1
        assert abs(box.xmax - 110) < 1
        assert abs(box.ymax - 120) < 1


def test_coco_nonexistent_file():
    result = CocoIO.read_all(Path("/nonexistent.json"), [])
    assert result == {}


def test_coco_empty_annotations():
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "annotations.json"
        CocoIO.write_all({}, json_path, [])
        restored = CocoIO.read_all(json_path, [])
        assert restored == {}
