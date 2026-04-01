from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_FILENAME = "alchemyannotate_project.json"


@dataclass
class ProjectConfig:
    """Session/project configuration persisted as JSON."""

    image_folder: str = ""
    annotation_format: str = "yolo"
    class_list: list[str] = field(default_factory=list)
    last_opened_image: str = ""
    annotation_output_folder: str = ""
    autosave_enabled: bool = True
    recently_used_class: str = ""

    def save(self, path: Path) -> None:
        data = {
            "image_folder": self.image_folder,
            "annotation_format": self.annotation_format,
            "class_list": self.class_list,
            "last_opened_image": self.last_opened_image,
            "annotation_output_folder": self.annotation_output_folder,
            "autosave_enabled": self.autosave_enabled,
            "recently_used_class": self.recently_used_class,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ProjectConfig:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()
        return cls(
            image_folder=data.get("image_folder", ""),
            annotation_format=data.get("annotation_format", "yolo"),
            class_list=data.get("class_list", []),
            last_opened_image=data.get("last_opened_image", ""),
            annotation_output_folder=data.get("annotation_output_folder", ""),
            autosave_enabled=data.get("autosave_enabled", True),
            recently_used_class=data.get("recently_used_class", ""),
        )
