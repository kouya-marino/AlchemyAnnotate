from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation


def test_bounding_box_properties():
    box = BoundingBox(class_name="cat", xmin=10, ymin=20, xmax=110, ymax=120)
    assert box.width == 100
    assert box.height == 100
    assert box.class_name == "cat"
    assert len(box.id) == 8


def test_bounding_box_roundtrip():
    box = BoundingBox(class_name="dog", xmin=5.5, ymin=10.5, xmax=50.5, ymax=80.5)
    d = box.to_dict()
    restored = BoundingBox.from_dict(d)
    assert restored.id == box.id
    assert restored.class_name == box.class_name
    assert restored.xmin == box.xmin
    assert restored.ymin == box.ymin
    assert restored.xmax == box.xmax
    assert restored.ymax == box.ymax


def test_image_annotation_roundtrip():
    ann = ImageAnnotation(
        image_filename="test.jpg",
        image_width=640,
        image_height=480,
        boxes=[
            BoundingBox(class_name="a", xmin=0, ymin=0, xmax=100, ymax=100),
            BoundingBox(class_name="b", xmin=200, ymin=200, xmax=300, ymax=300),
        ],
    )
    d = ann.to_dict()
    restored = ImageAnnotation.from_dict(d)
    assert restored.image_filename == "test.jpg"
    assert restored.image_width == 640
    assert restored.image_height == 480
    assert len(restored.boxes) == 2
    assert restored.boxes[0].class_name == "a"
    assert restored.boxes[1].class_name == "b"


def test_bounding_box_auto_id():
    b1 = BoundingBox()
    b2 = BoundingBox()
    assert b1.id != b2.id


def test_polygon_bounding_box():
    box = BoundingBox(
        class_name="cat",
        annotation_type="polygon",
        points=[[10, 20], [50, 10], [90, 60], [30, 80]],
    )
    box.compute_bbox_from_points()
    assert box.xmin == 10
    assert box.ymin == 10
    assert box.xmax == 90
    assert box.ymax == 80
    assert box.annotation_type == "polygon"


def test_polygon_roundtrip():
    box = BoundingBox(
        class_name="dog",
        annotation_type="polygon",
        points=[[100, 100], [200, 50], [150, 200]],
        xmin=100, ymin=50, xmax=200, ymax=200,
    )
    d = box.to_dict()
    assert d["annotation_type"] == "polygon"
    assert len(d["points"]) == 3

    restored = BoundingBox.from_dict(d)
    assert restored.annotation_type == "polygon"
    assert restored.points == box.points
    assert restored.xmin == box.xmin
    assert restored.ymax == box.ymax


def test_image_annotation_mixed_types_roundtrip():
    ann = ImageAnnotation(
        image_filename="test.jpg",
        image_width=640,
        image_height=480,
        boxes=[
            BoundingBox(class_name="a", xmin=0, ymin=0, xmax=100, ymax=100),
            BoundingBox(
                class_name="b",
                annotation_type="polygon",
                points=[[10, 10], [50, 10], [50, 50]],
                xmin=10, ymin=10, xmax=50, ymax=50,
            ),
        ],
    )
    d = ann.to_dict()
    restored = ImageAnnotation.from_dict(d)
    assert len(restored.boxes) == 2
    assert restored.boxes[0].annotation_type == "bbox"
    assert restored.boxes[1].annotation_type == "polygon"
    assert len(restored.boxes[1].points) == 3
