"""CNN soil-type classifier (ResNet-50) + Grad-CAM explainability.

torch/cv2/torchvision are imported lazily (inside functions, cached), not
at module load time. On this dev machine, Windows Application Control
blocks one of torch's native DLLs (_C.pyd) -- with a top-level `import
torch`, that crashes the whole FastAPI app at startup, since main.py
imports this module transitively through routers/analysis.py. Deferring
the import means the rest of the API (everything not touching the CNN
path) still boots and works; only an actual soil-type-from-photo call
hits the DLL block, and it fails with a clear error at that call site
instead of killing the server.

`from __future__ import annotations` makes all type hints (torch.Tensor,
etc.) lazy strings at runtime, so they don't require torch to be
imported just to define these function signatures. The `TYPE_CHECKING`
import below is never executed -- it exists purely so editors/Pylance
can resolve `torch.Tensor` while editing, without torch actually being
imported when Python runs this file.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    import torch

MODEL_PATH = Path(__file__).resolve().parent / "models" / "soil_classifier.pt"


@lru_cache(maxsize=1)
def _torch_modules():
    """Import torch/cv2/torchvision on first use, not at module load.

    Cached so the (potentially slow) import only happens once per process.
    If the Windows DLL block is active, this is where it will raise --
    at the point a CNN function is actually called, not at server startup.
    """
    import torch
    import torch.nn as nn
    import cv2
    from torchvision import models, transforms

    return torch, nn, cv2, models, transforms


@lru_cache(maxsize=1)
def _transform():
    torch, nn, cv2, models, transforms = _torch_modules()
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


@lru_cache(maxsize=1)
def _checkpoint():
    torch, nn, cv2, models, transforms = _torch_modules()
    ckpt = torch.load(MODEL_PATH, map_location="cpu")
    return ckpt["model_state_dict"], ckpt["class_names"]


@lru_cache(maxsize=1)
def _model():
    torch, nn, cv2, models, transforms = _torch_modules()
    state_dict, class_names = _checkpoint()
    model = models.resnet50(weights=None)
    num_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(0.3), nn.Linear(num_features, 128), nn.ReLU(),
        nn.Dropout(0.3), nn.Linear(128, len(class_names)),
    )
    model.load_state_dict(state_dict)
    model.eval()
    return model


def _class_names() -> list[str]:
    return _checkpoint()[1]


def _target_layer():
    return _model().layer4[-1]


def preprocess_image(pil_image: Image.Image) -> torch.Tensor:
    return _transform()(pil_image.convert("RGB"))


def predict(image_tensor: torch.Tensor) -> tuple[str, float]:
    torch, nn, cv2, models, transforms = _torch_modules()
    model = _model()
    with torch.no_grad():
        output = model(image_tensor.unsqueeze(0))
        probs = torch.softmax(output, dim=1)[0]
        idx = int(probs.argmax())
    return _class_names()[idx], float(probs[idx])


def gradcam_heatmap(model, image_tensor: torch.Tensor, target_layer):
    """Grad-CAM: which pixels drove the model's prediction for this image.

    Forward hook captures the target layer's activations; backward hook
    captures gradients flowing into it for the predicted class. Channels
    are weighted by their mean gradient, summed, ReLU'd, and normalised
    to produce a coarse heatmap of "where the evidence was".
    """
    torch, nn, cv2, models, transforms = _torch_modules()

    activations, gradients = [], []

    def fwd_hook(m, i, o):
        activations.append(o)

    def bwd_hook(m, gi, go):
        gradients.append(go[0])

    h1 = target_layer.register_forward_hook(fwd_hook)
    h2 = target_layer.register_full_backward_hook(bwd_hook)
    try:
        output = model(image_tensor.unsqueeze(0))
        pred_class = output.argmax(dim=1)
        model.zero_grad()
        output[0, pred_class].backward()
        acts = activations[0].squeeze(0)   # [C, H, W]
        grads = gradients[0].squeeze(0)    # [C, H, W]
        weights = grads.mean(dim=(1, 2))   # [C]
        cam = torch.relu((weights[:, None, None] * acts).sum(0))
        cam = cam / (cam.max() + 1e-8)
        return cam.detach().cpu().numpy(), pred_class.item()
    finally:
        h1.remove()
        h2.remove()


def encode_gradcam_overlay(cam: np.ndarray, image_tensor: torch.Tensor) -> dict:
    torch, nn, cv2, models, transforms = _torch_modules()

    # De-normalize the tensor back to a viewable image
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    img = image_tensor.permute(1, 2, 0).cpu().numpy()
    img = np.clip(std * img + mean, 0, 1)
    img_uint8 = (img * 255).astype(np.uint8)
    cam_resized = cv2.resize(cam, (img_uint8.shape[1], img_uint8.shape[0]))
    heatmap = cv2.applyColorMap((cam_resized * 255).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR), 0.6, heatmap, 0.4, 0)

    def _encode(arr):
        _, buf = cv2.imencode(".png", arr)
        return base64.b64encode(buf).decode("utf-8")

    return {
        "heatmap_png": _encode(heatmap),
        "overlay_png": _encode(overlay),
        "method": "Grad-CAM",
        "target_layer": "layer4[-1]",
    }