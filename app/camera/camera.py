"""
GestureOS — Camera Module

Wraps OpenCV VideoCapture with configurable resolution, FPS,
and an RGB conversion helper for MediaPipe.
"""

import cv2
import numpy as np

import config


class Camera:
    """Manages webcam capture and display."""

    def __init__(
        self,
        camera_index: int = config.CAMERA_INDEX,
        width: int = config.CAMERA_WIDTH,
        height: int = config.CAMERA_HEIGHT,
        fps: int = config.CAMERA_FPS,
    ):
        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam.")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def read(self) -> np.ndarray | None:
        """Read a BGR frame from the camera."""
        success, frame = self.cap.read()
        if not success:
            return None
        return frame

    def read_rgb(self) -> np.ndarray | None:
        """Read a frame and convert BGR → RGB (for MediaPipe)."""
        frame = self.read()
        if frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def show(self, frame: np.ndarray, window_name: str = "GestureOS") -> int:
        """Display a frame and return the pressed key (or -1)."""
        cv2.imshow(window_name, frame)
        return cv2.waitKey(1) & 0xFF

    def is_open(self) -> bool:
        return self.cap.isOpened()

    def release(self) -> None:
        self.cap.release()
        cv2.destroyAllWindows()