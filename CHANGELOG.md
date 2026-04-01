# Changelog

All notable changes to AlchemyAnnotate will be documented in this file.

## [1.1.0] - 2026-04-01

### Added
- Polygon annotation support: click vertices to draw, double-click to close, right-click/Escape to cancel
- Draw Polygon toolbar button (P shortcut), mutually exclusive with Draw Box (B)
- YOLOv8-seg format support: read/write polygon annotations as normalized vertex lists
- COCO segmentation field: read/write polygon annotations with `segmentation` data
- `PolygonItem` canvas rendering with selection highlight and color support
- `AnnotationType` enum (BBOX, POLYGON) in constants
- Geometry helpers: `polygon_bounding_rect`, `normalize_points`, `denormalize_points`, `clamp_points_to_image`
- Tests for polygon model roundtrip, YOLO-seg I/O, COCO segmentation I/O, geometry helpers

### Changed
- `BoundingBox` model extended with `annotation_type` and `points` fields
- Box list panel now shows polygon entries as "class: polygon (N pts)"
- Canvas controller supports `DRAWING_POLYGON` state
- Header label changed from "Boxes" to "Annotations (N)"

## [0.1.1] - 2026-04-01

### Added
- Toolbar with Draw Box (toggle), Delete Box, and Edit Class buttons
- Keyboard shortcuts: B (toggle draw), E (edit class of selected box)
- ClassSelectDialog: unified dialog to pick existing class or create a new one when drawing a box
- Draw mode toggle: disable drawing to select/inspect boxes without accidental draws
- Canvas draw enable/disable support

### Changed
- Drawing a bounding box now always prompts for class selection (dropdown + new class input)
- Removed silent "object" default class fallback
- Last used class is pre-selected in the class prompt dialog

### Fixed
- Boxes could be created without a valid class when no active class was set

## [0.1.0] - 2026-04-01

### Added
- Initial release
- Bounding box annotation on images loaded from a folder
- Sidebar image list with labeled/unlabeled status indicators
- Class management: create, delete, assign via UI
- Export in YOLO, Pascal VOC, and COCO formats (separate annotation folders)
- Autosave with 500ms debounce after every change
- Manual save with Ctrl+S
- Format switching with export/convert prompt
- Existing annotation detection on folder open
- Project session file (alchemyannotate_project.json)
- Zoom (Ctrl+Scroll), pan (middle-click drag), fit-to-window (Ctrl+0)
- Keyboard navigation: A/Left (prev), D/Right (next), Del (delete box)
- Unit tests for all IO formats, annotation model, and annotation store
