class Smoother:
    def __init__(
        self,
        alpha: float = 0.6,
    ):
        self.alpha = alpha
        self._x: float | None = None
        self._y: float | None = None
        self._angle: float | None = None
        self._started = False

    def smooth_position(self, x: float, y: float) -> tuple[float, float]:
        if not self._started:
            self._x = x
            self._y = y
            self._started = True
            return (x, y)

        if self._x is None or self._y is None:
            self._x = x
            self._y = y
            return (x, y)

        self._x = self.alpha * x + (1 - self.alpha) * self._x
        self._y = self.alpha * y + (1 - self.alpha) * self._y

        return (self._x, self._y)

    def smooth_angle(self, angle: float) -> float:
        if not self._started:
            self._angle = angle
            return angle

        if self._angle is None:
            self._angle = angle
            return angle

        self._angle = self.alpha * angle + (1 - self.alpha) * self._angle

        return self._angle

    def reset(self):
        self._x = None
        self._y = None
        self._angle = None
        self._started = False
