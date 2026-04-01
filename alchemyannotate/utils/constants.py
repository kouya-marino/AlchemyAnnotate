from enum import Enum

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


class AnnotationFormat(str, Enum):
    YOLO = "yolo"
    VOC = "voc"
    COCO = "coco"


ANNOTATION_FOLDER_NAMES = {
    AnnotationFormat.YOLO: "annotations_yolo",
    AnnotationFormat.VOC: "annotations_voc",
    AnnotationFormat.COCO: "annotations_coco",
}

# 20 distinct colors for class assignment
COLOR_PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]
