"""
Train a CNN to classify soil types from images using transfer learning.

Two-phase training (matches project standard):
  Phase 1: train only the new head, backbone frozen (15 epochs)
  Phase 2: unfreeze top backbone layers, fine-tune everything (10 epochs)

Dataset: inputs/Soil_large/Orignal-Dataset/<ClassName>/*.jpg
Outputs: app/ml/models/soil_classifier.pt
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report
from torch.optim import Adam
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = REPO_ROOT / "inputs" / "Soil_large" / "Orignal-Dataset"
MODEL_OUT_DIR = Path(__file__).resolve().parent / "models"
MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_OUT_PATH = MODEL_OUT_DIR / "soil_classifier.pt"

BATCH_SIZE = 8
PHASE1_EPOCHS = 15
PHASE2_EPOCHS = 10
HEAD_LR = 1e-3
FINE_TUNE_LR = 1e-5
IMAGE_SIZE = 224
VAL_SPLIT = 0.2

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")


def build_transforms():
    train_t = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(20),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    val_t = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    return train_t, val_t


def load_data():
    train_t, val_t = build_transforms()
    full = datasets.ImageFolder(str(DATA_DIR))
    class_names = full.classes
    print(f"Classes found ({len(class_names)}): {class_names}")
    print(f"Total images: {len(full)}")

    val_size = max(1, int(len(full) * VAL_SPLIT))
    train_size = len(full) - val_size
    train_idx, val_idx = random_split(
        full, [train_size, val_size], generator=torch.Generator().manual_seed(42)
    )

    train_ds = torch.utils.data.Subset(
        datasets.ImageFolder(str(DATA_DIR), transform=train_t), train_idx.indices
    )
    val_ds = torch.utils.data.Subset(
        datasets.ImageFolder(str(DATA_DIR), transform=val_t), val_idx.indices
    )

    # Class-balanced sampling — classes range widely in size (e.g. 52 to 284 images)
    train_labels = [full.samples[i][1] for i in train_idx.indices]
    class_counts = torch.bincount(torch.tensor(train_labels))
    class_weights = 1.0 / class_counts.float()
    sample_weights = [class_weights[label] for label in train_labels]
    sampler = torch.utils.data.WeightedRandomSampler(
        sample_weights, num_samples=len(sample_weights), replacement=True
    )

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, sampler=sampler)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)
    return train_loader, val_loader, class_names


def build_model(num_classes: int):
    model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    for p in model.parameters():
        p.requires_grad = False

    num_features = model.fc.in_features  # 2048 for ResNet-50
    model.fc = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(num_features, 128),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(128, num_classes),
    )
    return model.to(device)


def run_epoch(model, loader, criterion, optimizer=None):
    is_train = optimizer is not None
    model.train() if is_train else model.eval()
    total_loss, correct, total = 0.0, 0, 0

    context = torch.enable_grad() if is_train else torch.no_grad()
    with context:
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            if is_train:
                optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            if is_train:
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)
    return total_loss / total, correct / total


def evaluate_full(model, loader, class_names):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
    print("\nClassification Report:\n")
    print(classification_report(all_labels, all_preds, target_names=class_names, digits=2))
    acc = float(np.mean(np.array(all_preds) == np.array(all_labels)))
    return acc


def main():
    train_loader, val_loader, class_names = load_data()
    model = build_model(len(class_names))
    criterion = nn.CrossEntropyLoss()

    print("\nTRAINING STARTED (head only, backbone frozen)")
    print("=" * 60)
    optimizer = Adam(model.fc.parameters(), lr=HEAD_LR)
    best_val_acc, best_weights = 0.0, copy.deepcopy(model.state_dict())

    for epoch in range(PHASE1_EPOCHS):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion)
        print(f"Epoch {epoch+1}/{PHASE1_EPOCHS} - loss: {train_loss:.4f} - "
              f"accuracy: {train_acc:.4f} - val_loss: {val_loss:.4f} - val_accuracy: {val_acc:.4f}")
        if val_acc > best_val_acc:
            best_val_acc, best_weights = val_acc, copy.deepcopy(model.state_dict())

    print("\nFINE-TUNING (unfreezing top backbone layers)")
    print("=" * 60)
    for p in model.layer3.parameters():
        p.requires_grad = True
    for p in model.layer4.parameters():
        p.requires_grad = True

    optimizer = Adam([
        {"params": model.layer3.parameters(), "lr": FINE_TUNE_LR},
        {"params": model.layer4.parameters(), "lr": FINE_TUNE_LR},
        {"params": model.fc.parameters(), "lr": HEAD_LR},
    ])

    for epoch in range(PHASE2_EPOCHS):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion)
        print(f"Epoch {PHASE1_EPOCHS+epoch+1}/{PHASE1_EPOCHS+PHASE2_EPOCHS} - loss: {train_loss:.4f} - "
              f"accuracy: {train_acc:.4f} - val_loss: {val_loss:.4f} - val_accuracy: {val_acc:.4f}")
        if val_acc > best_val_acc:
            best_val_acc, best_weights = val_acc, copy.deepcopy(model.state_dict())

    model.load_state_dict(best_weights)

    print("\nTraining Completed Successfully!")
    torch.save({"model_state_dict": model.state_dict(), "class_names": class_names}, MODEL_OUT_PATH)
    print("Model Saved Successfully!")
    print(f"Location: {MODEL_OUT_PATH}")

    evaluate_full(model, val_loader, class_names)

    print("\n" + "=" * 60)
    print("CNN MODEL SUMMARY")
    print("=" * 60)
    print(model)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable:,} / {total:,}")


if __name__ == "__main__":
    main()