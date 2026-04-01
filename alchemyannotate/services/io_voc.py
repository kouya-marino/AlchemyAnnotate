from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation


class VocIO:
    """Read/write Pascal VOC XML annotation files."""

    @staticmethod
    def read(xml_path: Path) -> ImageAnnotation:
        if not xml_path.exists():
            return ImageAnnotation(image_filename=xml_path.stem)

        tree = ET.parse(xml_path)
        root = tree.getroot()

        filename = root.findtext("filename", xml_path.stem)
        size_el = root.find("size")
        width = int(size_el.findtext("width", "0")) if size_el is not None else 0
        height = int(size_el.findtext("height", "0")) if size_el is not None else 0

        annotation = ImageAnnotation(
            image_filename=filename,
            image_width=width,
            image_height=height,
        )

        for obj in root.findall("object"):
            class_name = obj.findtext("name", "unknown")
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.findtext("xmin", "0"))
            ymin = float(bndbox.findtext("ymin", "0"))
            xmax = float(bndbox.findtext("xmax", "0"))
            ymax = float(bndbox.findtext("ymax", "0"))
            annotation.boxes.append(BoundingBox(
                class_name=class_name,
                xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
            ))

        return annotation

    @staticmethod
    def write(annotation: ImageAnnotation, xml_path: Path) -> None:
        root = ET.Element("annotation")

        ET.SubElement(root, "folder").text = str(xml_path.parent.name)
        ET.SubElement(root, "filename").text = annotation.image_filename

        size = ET.SubElement(root, "size")
        ET.SubElement(size, "width").text = str(annotation.image_width)
        ET.SubElement(size, "height").text = str(annotation.image_height)
        ET.SubElement(size, "depth").text = "3"

        ET.SubElement(root, "segmented").text = "0"

        for box in annotation.boxes:
            obj = ET.SubElement(root, "object")
            ET.SubElement(obj, "name").text = box.class_name
            ET.SubElement(obj, "pose").text = "Unspecified"
            ET.SubElement(obj, "truncated").text = "0"
            ET.SubElement(obj, "difficult").text = "0"

            bndbox = ET.SubElement(obj, "bndbox")
            ET.SubElement(bndbox, "xmin").text = str(int(round(box.xmin)))
            ET.SubElement(bndbox, "ymin").text = str(int(round(box.ymin)))
            ET.SubElement(bndbox, "xmax").text = str(int(round(box.xmax)))
            ET.SubElement(bndbox, "ymax").text = str(int(round(box.ymax)))

        xml_path.parent.mkdir(parents=True, exist_ok=True)
        rough = ET.tostring(root, encoding="unicode")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        # Remove extra XML declaration from minidom
        lines = pretty.splitlines()
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        xml_path.write_text("\n".join(lines), encoding="utf-8")
