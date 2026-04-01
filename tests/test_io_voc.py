import tempfile
from pathlib import Path

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation
from alchemyannotate.services.io_voc import VocIO


def test_voc_write_read_roundtrip():
    ann = ImageAnnotation(
        image_filename="photo.jpg",
        image_width=640,
        image_height=480,
        boxes=[
            BoundingBox(class_name="cat", xmin=100, ymin=100, xmax=200, ymax=200),
            BoundingBox(class_name="dog", xmin=300, ymin=300, xmax=500, ymax=400),
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "photo.xml"
        VocIO.write(ann, xml_path)

        assert xml_path.exists()

        restored = VocIO.read(xml_path)
        assert restored.image_filename == "photo.jpg"
        assert restored.image_width == 640
        assert restored.image_height == 480
        assert len(restored.boxes) == 2
        assert restored.boxes[0].class_name == "cat"
        assert restored.boxes[0].xmin == 100
        assert restored.boxes[0].ymin == 100
        assert restored.boxes[0].xmax == 200
        assert restored.boxes[0].ymax == 200
        assert restored.boxes[1].class_name == "dog"


def test_voc_nonexistent_file():
    ann = VocIO.read(Path("/nonexistent.xml"))
    assert len(ann.boxes) == 0


def test_voc_empty_annotation():
    ann = ImageAnnotation(
        image_filename="empty.jpg",
        image_width=100,
        image_height=100,
        boxes=[],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "empty.xml"
        VocIO.write(ann, xml_path)
        restored = VocIO.read(xml_path)
        assert len(restored.boxes) == 0
        assert restored.image_width == 100
