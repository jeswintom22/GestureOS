"""
GestureOS — Hand Detector

Wraps the MediaPipe HandLandmarker (Tasks API) to extract 21 landmarks
per hand from a frame. Returns structured ``HandResult`` objects with
both normalised and pixel-space coordinates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

import config


@dataclass
class Landmark:
    """A single hand landmark in both normalised and pixel space."""
    x: float          # Normalised [0, 1]
    y: float          # Normalised [0, 1]
    z: float          # Depth (relative)
    px: int           # Pixel x
    py: int           # Pixel y


@dataclass
class HandResult:
    """Detection result for a single hand."""
    landmarks: list[Landmark]       # 21 landmarks
    handedness: str                  # "Left" or "Right"
    confidence: float               # Detection confidence [0, 1]


class HandDetector:
    """
    Detects hands in RGB frames using the MediaPipe Tasks API.

    Usage::

        detector = HandDetector()
        results = detector.detect(rgb_frame, frame_width, frame_height)
        for hand in results:
            print(hand.landmarks[8].px, hand.landmarks[8].py)  # Index tip
        detector.close()
    """

    # MediaPipe landmark indices for convenience
    WRIST = 0
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16
    PINKY_TIP = 20

    # Debug drawing colours (BGR)
    _CONNECTION_COLOR = (0, 200, 0)
    _LANDMARK_COLOR = (0, 0, 255)
    _CONNECTION_THICKNESS = 2
    _LANDMARK_RADIUS = 4

    def __init__(
        self,
        max_hands: int = config.MP_MAX_HANDS,
        min_detection_confidence: float = config.MP_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = config.MP_MIN_TRACKING_CONFIDENCE,
    ):
        model_path = config.MP_HAND_LANDMARKER_MODEL
        if not Path(model_path).is_file():
            raise FileNotFoundError(
                f"MediaPipe hand landmarker model not found at {model_path}. "
                "Download it from "
                "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                "hand_landmarker/float16/1/hand_landmarker.task "
                "and place it at that path."
            )

        options = vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        # HAND_CONNECTIONS yields Connection dataclasses (`.start` / `.end`),
        # not plain tuples like the legacy solutions API. Normalise to tuples
        # so callers can unpack them as (idx_a, idx_b).
        self._connections = [
            (conn.start, conn.end)
            for conn in vision.HandLandmarksConnections.HAND_CONNECTIONS
        ]
        self._last_ts_ms: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        rgb_frame: np.ndarray,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> list[HandResult]:
        """
        Process an RGB frame and return detected hands.

        Parameters
        ----------
        rgb_frame : np.ndarray
            The input frame in RGB colour space (uint8, C-contiguous).
        frame_width, frame_height : int, optional
            Pixel dimensions for coordinate conversion.
            Inferred from ``rgb_frame.shape`` if not provided.

        Returns
        -------
        list[HandResult]
        """
        if frame_width is None:
            frame_height, frame_width = rgb_frame.shape[:2]

        result = self._landmarker.detect_for_video(
            self._to_mp_image(rgb_frame),
            self._next_timestamp_ms(),
        )

        hands: list[HandResult] = []

        if not result.hand_landmarks:
            return hands

        for lm_list, handedness in zip(result.hand_landmarks, result.handedness):
            landmarks = [
                Landmark(
                    x=lm.x,
                    y=lm.y,
                    z=lm.z,
                    px=int(lm.x * frame_width),
                    py=int(lm.y * frame_height),
                )
                for lm in lm_list
            ]

            hands.append(
                HandResult(
                    landmarks=landmarks,
                    handedness=handedness[0].category_name,  # "Left" / "Right"
                    confidence=handedness[0].score,
                )
            )

        return hands

    def draw(
        self,
        bgr_frame: np.ndarray,
        rgb_frame: np.ndarray,
    ) -> np.ndarray:
        """
        Draw hand landmarks and connections on a BGR frame (debug preview).

        Parameters
        ----------
        bgr_frame : np.ndarray
            The frame to draw on (BGR).
        rgb_frame : np.ndarray
            The same frame in RGB that was passed to ``detect()``.

        Returns
        -------
        np.ndarray
            The annotated BGR frame.
        """
        result = self._landmarker.detect_for_video(
            self._to_mp_image(rgb_frame),
            self._next_timestamp_ms(),
        )
        if not result.hand_landmarks:
            return bgr_frame

        h, w = bgr_frame.shape[:2]
        for lm_list in result.hand_landmarks:
            points = [(int(lm.x * w), int(lm.y * h)) for lm in lm_list]

            for idx_a, idx_b in self._connections:
                cv2.line(
                    bgr_frame,
                    points[idx_a],
                    points[idx_b],
                    self._CONNECTION_COLOR,
                    self._CONNECTION_THICKNESS,
                )
            for x, y in points:
                cv2.circle(
                    bgr_frame,
                    (x, y),
                    self._LANDMARK_RADIUS,
                    self._LANDMARK_COLOR,
                    -1,
                )
        return bgr_frame

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._landmarker.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_mp_image(rgb_frame: np.ndarray) -> mp.Image:
        """Wrap an RGB uint8 frame into a MediaPipe Image."""
        # MediaPipe requires a C-contiguous uint8 array.
        data = np.ascontiguousarray(rgb_frame)
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=data)

    def _next_timestamp_ms(self) -> int:
        """
        Return a strictly increasing timestamp (ms) for VIDEO-mode inference.

        VIDEO mode rejects non-increasing timestamps, and wall-clock time
        can repeat between frames, so enforce monotonicity here.
        """
        now = int(time.time() * 1000)
        if now <= self._last_ts_ms:
            now = self._last_ts_ms + 1
        self._last_ts_ms = now
        return now
