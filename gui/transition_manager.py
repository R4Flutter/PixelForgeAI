# gui/transition_manager.py
"""
Cinematic transition manager for PixelForgeAI.
Provides a fade + slide animation when navigating between pages in the
QStackedWidget. The animation respects the ``PIXELFORGEAI_REDUCED_MOTION``
environment variable – when set, the transition occurs instantly.
Optionally, depth‑layer widgets (e.g. background glow) can be faded together
with the page transition.

Usage (from ``MainWindow.__init__``)::

    self._transition = TransitionManager(self)
    # optionally register depth‑layer widgets
    # self._transition.set_depth_layers(self._bg, self._ambient)

    # In the navigation method:
    self._transition.cinematic_transition(outgoing, incoming,
                                          direction="left",
                                          on_finished=_set_index)
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QObject,
    QPoint,
)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
import os


def _reduced_motion() -> bool:
    """Return ``True`` if the user prefers reduced motion.

    The application already uses the same env‑var ``PIXELFORGEAI_REDUCED_MOTION``
    in other places, so we mirror that logic here.
    """
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in (
        "",
        "0",
        "false",
    )


class TransitionManager(QObject):
    """Utility class to animate page transitions.

    The class holds optional references to *depth‑layer* widgets that should be
    dimmed during a transition. If ``set_depth_layers`` is not called, only the
    page widgets are animated.
    """

    _NAV_DURATION_MS = 260  # matches existing navigation fade duration

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bg_layer: Optional[QWidget] = None
        self._ambient_layer: Optional[QWidget] = None
        self._current_group = None  # keep animation alive until it finishes

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def set_depth_layers(self, bg: QWidget, ambient: QWidget) -> None:
        """Register background/ambient widgets to be faded during transitions.

        ``bg`` and ``ambient`` are the depth‑layer widgets created by ``HomePage``
        (e.g. ``AnimatedBg`` and ``AmbientGlow``). The manager will animate their
        opacity from 1.0 → 0.3 → 1.0 together with the page fade/slide.
        """
        self._bg_layer = bg
        self._ambient_layer = ambient

    def cinematic_transition(
        self,
        outgoing: QWidget,
        incoming: QWidget,
        direction: str = "left",
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Perform a fade + slide transition between two pages.

        Parameters
        ----------
        outgoing: QWidget
            Currently visible page.
        incoming: QWidget
            Page that will become visible.
        direction: {"left", "right"}
            ``"left"`` makes the incoming page slide in from the right side of the
            container (forward navigation). ``"right"`` slides it in from the
            left (backward navigation).
        on_finished: Callable, optional
            Callback executed after the animation finishes – typically used to
            call ``self._stack.setCurrentIndex(idx)``.
        """
        if _reduced_motion():
            # Instant switch – hide outgoing, show incoming, invoke callback.
            outgoing.hide()
            incoming.show()
            if on_finished:
                on_finished()
            return

        # -----------------------------------------------------------------
        # Prepare opacity effects for both pages.
        # -----------------------------------------------------------------
        out_eff = QGraphicsOpacityEffect(outgoing)
        out_eff.setOpacity(1.0)
        outgoing.setGraphicsEffect(out_eff)

        in_eff = QGraphicsOpacityEffect(incoming)
        in_eff.setOpacity(0.0)
        incoming.setGraphicsEffect(in_eff)
        incoming.show()

        # -----------------------------------------------------------------
        # Geometry for slide animation.
        # -----------------------------------------------------------------
        parent_rect = outgoing.parent().rect()
        start_x = parent_rect.width() if direction == "left" else -parent_rect.width()
        incoming.move(start_x, 0)

        # Fade out outgoing page.
        fade_out = QPropertyAnimation(out_eff, b"opacity", outgoing)
        fade_out.setDuration(self._NAV_DURATION_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.OutCubic)

        # Fade in incoming page.
        fade_in = QPropertyAnimation(in_eff, b"opacity", incoming)
        fade_in.setDuration(self._NAV_DURATION_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)

        # Slide incoming page.
        slide = QPropertyAnimation(incoming, b"pos", incoming)
        slide.setDuration(self._NAV_DURATION_MS)
        slide.setStartValue(QPoint(start_x, 0))
        slide.setEndValue(QPoint(0, 0))
        slide.setEasingCurve(QEasingCurve.OutCubic)

        # -----------------------------------------------------------------
        # Optional depth‑layer fade (dim background during transition).
        # -----------------------------------------------------------------
        depth_anims = []
        if self._bg_layer is not None:
            bg_eff = QGraphicsOpacityEffect(self._bg_layer)
            bg_eff.setOpacity(1.0)
            self._bg_layer.setGraphicsEffect(bg_eff)
            bg_fade = QPropertyAnimation(bg_eff, b"opacity", self._bg_layer)
            bg_fade.setDuration(self._NAV_DURATION_MS)
            bg_fade.setStartValue(1.0)
            bg_fade.setEndValue(0.3)
            bg_fade.setEasingCurve(QEasingCurve.OutCubic)
            depth_anims.append(bg_fade)
        if self._ambient_layer is not None:
            amb_eff = QGraphicsOpacityEffect(self._ambient_layer)
            amb_eff.setOpacity(1.0)
            self._ambient_layer.setGraphicsEffect(amb_eff)
            amb_fade = QPropertyAnimation(amb_eff, b"opacity", self._ambient_layer)
            amb_fade.setDuration(self._NAV_DURATION_MS)
            amb_fade.setStartValue(1.0)
            amb_fade.setEndValue(0.3)
            amb_fade.setEasingCurve(QEasingCurve.OutCubic)
            depth_anims.append(amb_fade)

        # -----------------------------------------------------------------
        # Assemble the parallel animation group.
        # -----------------------------------------------------------------
        group = QParallelAnimationGroup()
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        group.addAnimation(slide)
        for a in depth_anims:
            group.addAnimation(a)

        # Cleanup after the animation finishes.
        def _cleanup() -> None:
            self._current_group = None
            outgoing.setGraphicsEffect(None)
            incoming.setGraphicsEffect(None)
            if self._bg_layer is not None:
                self._bg_layer.setGraphicsEffect(None)
            if self._ambient_layer is not None:
                self._ambient_layer.setGraphicsEffect(None)
            if on_finished:
                on_finished()
            incoming.show()

        group.finished.connect(_cleanup)
        self._current_group = group
        group.start(QAbstractAnimation.DeleteWhenStopped)
