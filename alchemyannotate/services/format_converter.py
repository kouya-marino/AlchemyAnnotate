from __future__ import annotations

from pathlib import Path

from alchemyannotate.services.io_router import IORouter
from alchemyannotate.utils.constants import AnnotationFormat


class FormatConverter:
    """Batch convert annotations from one format to another."""

    @staticmethod
    def convert(
        base_folder: Path,
        source_format: AnnotationFormat,
        target_format: AnnotationFormat,
        image_list: list[str],
        image_sizes: dict[str, tuple[int, int]],
        class_list: list[str],
    ) -> None:
        """Read all annotations from source format, write in target format."""
        source_router = IORouter(base_folder, source_format)
        target_router = IORouter(base_folder, target_format)

        all_anns = source_router.load_all(image_list, image_sizes, class_list)
        if all_anns:
            target_router.save_all(all_anns, class_list)
