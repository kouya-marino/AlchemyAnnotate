import tempfile
from pathlib import Path

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation
from alchemyannotate.services.io_yolo import YoloIO


def test_yolo_write_read_roundtrip():
    ann = ImageAnnotation(
        image_filename="photo.jpg",
        image_width=640,
        image_height=480,
        boxes=[
            BoundingBox(class_name="cat", xmin=100, ymin=100, xmax=200, ymax=200),
            BoundingBox(class_name="dog", xmin=300, ymin=300, xmax=500, ymax=400),
        ],
    )
    class_list = ["cat", "dog"]

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = Path(tmpdir) / "photo.txt"
        YoloIO.write(ann, txt_path, class_list)

        assert txt_path.exists()
        content = txt_path.read_text()
        lines = content.strip().splitlines()
        assert len(lines) == 2

        # Read back
        restored = YoloIO.read(txt_path, 640, 480, class_list)
        assert len(restored.boxes) == 2
        assert restored.boxes[0].class_name == "cat"
        assert restored.boxes[1].class_name == "dog"

        # Check coordinates are approximately correct (floating point)
        assert abs(restored.boxes[0].xmin - 100) < 1
        assert abs(restored.boxes[0].ymin - 100) < 1
        assert abs(restored.boxes[0].xmax - 200) < 1
        assert abs(restored.boxes[0].ymax - 200) < 1


def test_yolo_classes_txt():
    class_list = ["person", "car", "bicycle"]

    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        YoloIO.write_classes_txt(class_list, folder)

        restored = YoloIO.read_classes_txt(folder)
        assert restored == class_list


def test_yolo_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = Path(tmpdir) / "empty.txt"
        txt_path.write_text("")
        ann = YoloIO.read(txt_path, 640, 480, ["cat"])
        assert len(ann.boxes) == 0


def test_yolo_nonexistent_file():
    ann = YoloIO.read(Path("/nonexistent.txt"), 640, 480, ["cat"])
    assert len(ann.boxes) == 0
