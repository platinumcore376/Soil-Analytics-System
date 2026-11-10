# Datasets (Phase 1, item 1.8)

## 1. Structured soil / crop data — ✅ acquired

`crop_recommendation.csv` — Kaggle: [Crop Recommendation Dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset)
- 2,200 rows, 22 crops. Columns: `N, P, K, temperature, humidity, ph, rainfall, label`.
- Used by [notebooks/structured_xgboost.ipynb](../notebooks/structured_xgboost.ipynb).

## 2. Labeled soil imagery — CNN training

Already used to train the ResNet-50 in [notebooks/cnn_soil_type.ipynb](../notebooks/cnn_soil_type.ipynb):
- **Roboflow — Soil Type Identification** (5 classes: Black, Cinder, Laterite, Peat, Yellow), ~4,200 images.

### Additional open sources to curate (per documentation)

| Source | Content | Access |
|--------|---------|--------|
| **ICAR** (Indian Council of Agricultural Research) | Indian soil profiles, Soil Health Card data | https://icar.org.in / https://soilhealth.dac.gov.in |
| **USDA NRCS** | Soil survey imagery & taxonomy | https://www.nrcs.usda.gov/resources/data-and-reports |
| **data.gov.in** | District-level Soil Health Card NPK/pH | https://data.gov.in (search "soil health card") |
| **Kaggle — Soil types / Soil Fertility** | Additional labeled soil imagery | https://www.kaggle.com/datasets |

### Curation guidance
- Organize images as `ImageFolder` layout: `data/images/<split>/<class>/*.jpg` (train/valid/test).
- Run every image through the ingestion preprocessing (`backend/app/preprocessing.py`)
  before training so training and inference distributions match:
  color correction → resize → optional background removal.
- Use `preprocessing.augment()` for feature-preserving augmentation (geometric + mild
  brightness only — no hue shifts that would destroy nutrient color cues).

> Large image corpora are **not** committed to git. Store locally under `data/images/`
> (git-ignored) or in cloud object storage (S3/GCS) as noted for Phase 3.
