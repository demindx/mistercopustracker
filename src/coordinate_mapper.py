from src.obs_connector import SceneItemTransform


class CoordinateMapper:
    def __init__(self, canvas_width: int, canvas_height: int):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self._webcam_transform: SceneItemTransform | None = None

    def update_webcam_transform(self, transform: SceneItemTransform):
        self._webcam_transform = transform

    def map_to_canvas(
        self,
        face_norm_x: float,
        face_norm_y: float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[float, float] | None:
        if self._webcam_transform is None:
            return (face_norm_x * self.canvas_width,
                    face_norm_y * self.canvas_height)

        t = self._webcam_transform

        face_px = face_norm_x * frame_width
        face_py = face_norm_y * frame_height

        source_face_px = face_px * (t.source_width / frame_width)
        source_face_py = face_py * (t.source_height / frame_height)

        cropped_width = t.source_width - t.crop_left - t.crop_right
        cropped_height = t.source_height - t.crop_top - t.crop_bottom

        if cropped_width <= 0 or cropped_height <= 0:
            return (face_norm_x * self.canvas_width,
                    face_norm_y * self.canvas_height)

        norm_in_crop_x = (source_face_px - t.crop_left) / cropped_width
        norm_in_crop_y = (source_face_py - t.crop_top) / cropped_height

        if norm_in_crop_x < 0 or norm_in_crop_x > 1:
            return None
        if norm_in_crop_y < 0 or norm_in_crop_y > 1:
            return None

        displayed_w = cropped_width * t.scale_x
        displayed_h = cropped_height * t.scale_y

        display_local_x = norm_in_crop_x * displayed_w
        display_local_y = norm_in_crop_y * displayed_h

        top_left_x, top_left_y = self._source_top_left(t, displayed_w, displayed_h)

        canvas_x = top_left_x + display_local_x
        canvas_y = top_left_y + display_local_y

        return (canvas_x, canvas_y)

    @staticmethod
    def _source_top_left(
        transform: SceneItemTransform,
        displayed_w: float,
        displayed_h: float,
    ) -> tuple[float, float]:
        alignment = transform.alignment

        horizontal = alignment & 3
        if horizontal == 1:
            left_x = transform.pos_x
        elif horizontal == 2:
            left_x = transform.pos_x - displayed_w
        else:
            left_x = transform.pos_x - displayed_w / 2

        vertical = alignment & 12
        if vertical == 4:
            top_y = transform.pos_y
        elif vertical == 8:
            top_y = transform.pos_y - displayed_h
        else:
            top_y = transform.pos_y - displayed_h / 2

        return (left_x, top_y)

    def map_rotation(self, face_roll: float) -> float:
        return face_roll
