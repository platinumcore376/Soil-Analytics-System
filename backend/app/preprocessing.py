"""OpenCV-based image preprocessing (Phase 1, items 1.5 & 1.7).

Pipeline:
  validate -> normalize format -> resize -> color correction -> background removal
Plus feature-preserving augmentation helpers for the training pipeline.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


# --------------------------------------------------------------------------- #
# Validation / normalization (item 1.5)
# --------------------------------------------------------------------------- #
def read_image(path: str | Path) -> np.ndarray:
    """Load an image as BGR. Raises ValueError if unreadable/corrupt."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not decode image: {path}")
    return img


def resize_max(img: np.ndarray, target: int = 1024) -> np.ndarray:
    """Resize so the longest side == target, preserving aspect ratio."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= target:
        return img
    scale = target / longest
    new_size = (int(round(w * scale)), int(round(h * scale)))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)


# --------------------------------------------------------------------------- #
# Color correction (item 1.7)
# --------------------------------------------------------------------------- #
def gray_world_white_balance(img: np.ndarray) -> np.ndarray:
    """Gray-world white balance — removes color casts from phone cameras."""
    result = img.astype(np.float32)
    avg_b, avg_g, avg_r = (result[:, :, c].mean() for c in range(3))
    avg_gray = (avg_b + avg_g + avg_r) / 3.0
    for c, avg in enumerate((avg_b, avg_g, avg_r)):
        if avg > 0:
            result[:, :, c] *= avg_gray / avg
    return np.clip(result, 0, 255).astype(np.uint8)


def clahe_contrast(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization on the L channel (LAB)."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def color_correct(img: np.ndarray) -> np.ndarray:
    return clahe_contrast(gray_world_white_balance(img))


# --------------------------------------------------------------------------- #
# Background removal (item 1.7)
# --------------------------------------------------------------------------- #
def remove_background(img: np.ndarray) -> np.ndarray:
    """GrabCut foreground extraction. Isolates the soil sample from surroundings.

    Returns a BGR image with the background set to black. Falls back to the
    original image if GrabCut fails to find a confident foreground.
    """
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    # Assume the subject occupies the central region.
    margin_x, margin_y = int(w * 0.05), int(h * 0.05)
    rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

    try:
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return img

    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(
        "uint8"
    )
    if fg_mask.sum() < 0.05 * h * w:  # too little foreground -> unreliable
        return img
    return img * fg_mask[:, :, np.newaxis]


# --------------------------------------------------------------------------- #
# Full inference preprocessing
# --------------------------------------------------------------------------- #
def preprocess_for_inference(
    src_path: str | Path,
    dst_path: str | Path,
    target_size: int = 1024,
    do_bg_removal: bool = True,
) -> dict:
    """Run the full pipeline and write the processed image to dst_path.

    Returns metadata: {width, height, processed_path}.
    """
    img = read_image(src_path)
    img = resize_max(img, target_size)
    img = color_correct(img)
    if do_bg_removal:
        img = remove_background(img)

    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst_path), img)

    h, w = img.shape[:2]
    return {"width": w, "height": h, "processed_path": str(dst_path)}


# --------------------------------------------------------------------------- #
# Feature-preserving augmentation for the training pipeline (item 1.7)
# --------------------------------------------------------------------------- #
def augment(img: np.ndarray, seed: int | None = None) -> list[np.ndarray]:
    """Return augmentations that preserve soil color/texture cues.

    Deliberately avoids hue shifts and heavy blur that would destroy the
    nutrient-relevant color signal. Geometric flips/rotations + mild brightness.
    """
    rng = np.random.default_rng(seed)
    out = [img]

    out.append(cv2.flip(img, 1))   # horizontal
    out.append(cv2.flip(img, 0))   # vertical

    for angle in (90, 270):
        m = cv2.getRotationMatrix2D(
            (img.shape[1] / 2, img.shape[0] / 2), angle, 1.0
        )
        out.append(cv2.warpAffine(img, m, (img.shape[1], img.shape[0])))

    # Mild brightness jitter (multiplicative), texture-preserving.
    factor = float(rng.uniform(0.85, 1.15))
    out.append(np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8))

    return out
