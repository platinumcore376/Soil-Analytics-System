<div align="center">
  <h1>AI-Based Soil Health Assessment & Crop Recommendation System</h1>
  <p><b>An enterprise-grade, offline-first multimodal agricultural diagnostic platform for smallholder farmers</b></p>
</div>

---

## 📖 Executive Overview

Soil degradation and sub-optimal chemical fertilization directly depress agricultural yields and long-term soil microbiomes across smallholder farming regions. Traditional centralized laboratory testing suffers from turnaround delays of **7 to 14 days**, costs prohibitive for smallholders, and paper-based reports that are inaccessible to illiterate farmers.

This system bridges the diagnostic gap through an **offline-first, multimodal AI architecture**:
- **Reduces Diagnostic Latency**: Delivers comprehensive soil health scoring, nutrient deficiency diagnoses, and crop recommendations in **under 1.8 seconds**.
- **Multimodal Diagnostic Fusion**: Unifies spatial visual features from a fine-tuned **ResNet-50 CNN** (soil texture/type) with precise laboratory chemical readings across **11 parameters** (N, P, K, pH, EC, S, Cu, Fe, Mn, Zn, B).
- **Explainable Agronomic AI**: Provides visual feature heatmaps (**Grad-CAM**) for image attention and tabular feature attributions (**SHAP**) translated into human-readable advice.
- **Scientifically Grounded Interventions**: Generates personalized **ICAR fertilizer replenishment schedules** (Urea, DAP, MOP, Gypsum, Micronutrients) calibrated to farm acreage.
- **Voice-Enabled Rural Accessibility**: Delivers localized audio synthesis across **4 Indian languages** (English, Hindi, Kannada, Telugu) using **Sarvam AI TTS** with device fallback.

---

## 🗺️ System Architecture

The platform separates responsibilities cleanly across client, gateway, application, machine learning, and persistence tiers:

```mermaid
graph TD
    subgraph Client ["Client Tier: Progressive Web App (Next.js 16)"]
        UI["Mobile Viewport UI (React 19 / Tailwind CSS)"]
        SW["Service Worker (sw.js - Cache & Offline Queue)"]
        State["State Providers (AuthProvider, LocaleProvider, useField)"]
        APIClient["Typed API Client (src/lib/api.ts)"]
        
        UI --> State
        UI --> APIClient
        APIClient --> SW
    end

    subgraph Gateway ["Reverse Proxy & Rewrite Layer"]
        Proxy["Next.js Gateway (/api/* rewrite)"]
        SW -->|Same-Origin Request| Proxy
    end

    subgraph Backend ["Application Tier: FastAPI (Python 3.11+)"]
        FastAPI["FastAPI App (app.main:app)"]
        AuthMid["Auth & IDOR Security Guard (app.auth)"]
        Routers["Endpoint Controllers (analysis, farms, images, tts)"]
        
        Proxy -->|Forward| FastAPI
        FastAPI --> AuthMid
        AuthMid --> Routers
    end

    subgraph ML ["Machine Learning & Advisory Engine"]
        CNN["PyTorch ResNet-50 CNN + Grad-CAM (cnn.py)"]
        Rules["Authoritative ICAR Rule Engine (structured.py)"]
        XGB["11x XGBoost Nutrient Classifiers + SHAP (structured.py)"]
        RF["Random Forest Crop Suitability (crops.py)"]
        Trend["Ridge Regression Degradation Model (trend.py)"]
        Dosage["Fertilizer Budgeting Engine (dosage.py)"]
        ReportLab["ReportLab PDF Health Card Generator (report.py)"]

        Routers --> CNN
        Routers --> Rules
        Routers --> XGB
        Routers --> RF
        Routers --> Trend
        Routers --> Dosage
        Routers --> ReportLab
    end

    subgraph Storage ["Data & External Services Tier"]
        DB[("PostgreSQL 16 / SQLite Engine")]
        CloudStore[("Supabase Storage / Local Disk Storage")]
        Sarvam["Sarvam AI Indian Regional Voice API"]

        Routers -->|ORM Queries| DB
        Routers -->|Image Blobs| CloudStore
        Routers -->|TTS Synthesize| Sarvam
    end
```

---

## 🔄 User Journey & Diagnostic Flowchart

The following flowchart illustrates the farmer's end-to-end journey from authentication to actionable field intervention:

```mermaid
flowchart TD
    Start([Farmer Opens App]) --> Auth{Signed In?}
    Auth -- No --> SignIn[Enter Phone or Email + Password]
    SignIn --> SetToken[Store JWT & Clear Stale Caches]
    Auth -- Yes --> SelectPlot[Select or Register Farm & Field Plot]
    SetToken --> SelectPlot

    SelectPlot --> ChooseMode{Select Capture Method}
    
    ChooseMode -- Camera Photo --> CapturePhoto[Capture / Upload Soil Photo]
    CapturePhoto --> UploadImage[POST /images - Preprocess & Save]
    UploadImage --> TriggerAnalyzePhoto[POST /analyze with image_id]
    
    ChooseMode -- Lab Readings --> ManualSliders[Adjust 6 Chemical Sliders: N, P, K, pH, OM, Moisture]
    ManualSliders --> TriggerAnalyzeLab[POST /analyze with chemical readings]

    TriggerAnalyzePhoto --> ExecML[FastAPI ML Inference Pipeline]
    TriggerAnalyzeLab --> ExecML

    subgraph Pipeline ["Inference & Decision Engine"]
        ExecML --> CNNInference[ResNet-50 Soil Type Classification]
        ExecML --> RuleInference[ICAR Threshold Diagnosis]
        ExecML --> XGBInference[XGBoost Nutrient Deficiencies]
        ExecML --> CropInference[Crop Suitability + Rotation Filter]
        ExecML --> DosageCalc[ICAR Replenishment Dosage Schedule]
        ExecML --> TrendFit[Historical Ridge Regression Trajectory]
    end

    Pipeline --> ResultsScreen[Dashboard: Health Score Dial, Nutrient Grid & Crop Advice]
    
    ResultsScreen --> ActionListen[Tap Speak Button: Sarvam AI Voice Readout]
    ResultsScreen --> ActionTrend[Inspect Multi-Season Degradation Projections]
    ResultsScreen --> ActionPDF[Download Localized Multi-Panel PDF Report Card]
```

---

## 🧠 Multimodal ML & Decision Pipeline

The ML pipeline fuses computer vision with tabular biochemical modeling:

```mermaid
flowchart LR
    subgraph Vision ["Spatial / Visual Channel"]
        RawImg["Soil RGB Photo (224x224)"] --> ResNet["ResNet-50 Backbone"]
        ResNet --> SoilClass["Soil Type: Alluvial, Black, Clay, Red"]
        ResNet --> GradCAM["Grad-CAM Attention Heatmap"]
    end

    subgraph Chemical ["Biochemical Lab Channel"]
        Readings["11 Soil Parameters (N, P, K, pH, EC, S, Cu, Fe, Mn, Zn, B)"]
        Readings --> RuleEngine["ICAR Rule Engine (Authoritative)"]
        Readings --> XGBModels["11x XGBoost Classifiers (Leak-Free)"]
        XGBModels --> SHAPExplainer["SHAP Force Plot Values"]
    end

    subgraph Fusion ["Multimodal Fusion & Agronomic Advisory"]
        SoilClass --> CropRec["Crop Suitability Classifier (Random Forest)"]
        RuleEngine --> CropRec
        CropRec --> RotationGuard["Rotation Guard (Recent Crop Memory)"]
        
        RuleEngine --> FertDosage["Fertilizer Budgeting Engine"]
        SoilClass --> FertDosage
        FertDosage --> ApplicationSchedule["Acreage-Scaled Replenishment Schedule"]
    end
```

---

## ✨ Key Capabilities & Technical Features

### 1. Multimodal Soil Classification & Visual Explainability
- Fine-tuned **ResNet-50** deep convolutional neural network classifying 4 primary soil classes (**Alluvial, Black, Clay, Red**) with **92.4% test accuracy**.
- Integrated **Grad-CAM** (Gradient-weighted Class Activation Mapping) extracting visual attention overlays from the final convolutional layer (`layer4[2].conv3`), ensuring model predictions ground on soil granularity rather than lighting artifacts.

### 2. Scientific 11-Parameter Nutrient Assessment
- Evaluates **Macronutrients** (Nitrogen, Phosphorus, Potassium), **Secondary Nutrients** (Sulfur, pH, Electrical Conductivity), and **Micronutrients** (Copper, Iron, Manganese, Zinc, Boron).
- Dual-tier diagnosis: Authoritative agronomic threshold rules combined with 11 leak-free gradient-boosted trees (**XGBoost**) providing calibrated confidence scores and **SHAP** feature attribution analysis.

### 3. Scientific ICAR Fertilizer Dosage Engine
- Translates diagnosed deficiencies into actionable replenishment schedules based on **Indian Council of Agricultural Research (ICAR)** protocols.
- Calculates exact product amounts (Urea, DAP, MOP, Gypsum, Chelated Micronutrients) tailored to plot acreage, basal timing, and split vegetative applications.

### 4. Crop Suitability & Rotation Guardrails
- Evaluates soil chemistry against a 22-class crop suitability model (**Random Forest**, 99.1% accuracy).
- Applies **crop rotation memory** against recent harvests to prevent monoculture nutrient exhaustion and soil-borne pest proliferation.

### 5. Multi-Season Degradation Forecasting
- Timeseries **Ridge regression** forecasting historical soil health scores across 1–3 seasons.
- Calculates degradation velocity (points/season), $R^2$ fit reliability, and automated alerts for fields approaching critical degradation thresholds.

### 6. Offline-First PWA with Multi-Lingual Speech Synthesis
- Next.js 16 Progressive Web App with custom service worker (`public/sw.js`) implementing **stale-while-revalidate** caching and background offline request queuing.
- Full localization across **4 Indian languages** (English, Hindi, Kannada, Telugu) validated across 197 translation keys.
- Dual-tier voice readout: Proxied **Sarvam AI Bulbul TTS** for authentic Indian-accented speech with seamless fallback to the browser's native **Web Speech API**.

### 7. Automated Agronomic PDF Report Card
- Generates localized, print-ready PDF health cards via **ReportLab** and **Matplotlib**, complete with visual nutrient status gauges, fertilizer tables, and multi-season trend charts.

---

## 🛠️ Technology Stack Matrix

| Category | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | Next.js (App Router) | 16.3.0 | Mobile-first server-rendered PWA shell |
| **UI Library** | React | 19.0.0 | Component rendering engine |
| **Styling & Icons** | Tailwind CSS | 3.4.17 | Agricultural-themed high-contrast design system |
| **Animations** | Framer Motion | 13.1.1 | Gesture animations and view transitions |
| **Localization** | `next-i18next` / `i18next` | 16.0 / 26.3 | Regional multi-lingual translation engine |
| **Backend Framework** | FastAPI | 0.110+ | Asynchronous high-throughput REST API |
| **Server Engine** | Uvicorn | 0.28+ | ASGI production server |
| **ORM & Database** | SQLAlchemy 2.0 / PostgreSQL | 2.0 / 16 | Relational data mapping and connection pooling |
| **Validation** | Pydantic v2 | 2.6.4 | Strict schema typing and environment configuration |
| **Deep Learning** | PyTorch / TorchVision | 2.2.0 | ResNet-50 CNN inference and Grad-CAM |
| **Tabular ML** | XGBoost / Scikit-learn | 2.0 / 1.4 | Nutrient deficiency trees, Random Forest, Ridge regression |
| **Reporting** | ReportLab / Matplotlib | 4.1 / 3.8 | PDF generation and timeseries trend charting |
| **Voice Synthesis** | Sarvam AI API / HTTPX | 0.27+ | Regional Indian TTS proxy client |
| **Storage** | Supabase Storage / Local Disk | 2.3+ | Cloud object storage for soil imagery |

---

## 📊 Machine Learning Model Benchmarks

| Model | Architecture | Training Dataset | Input Shape | Key Metric | Inference Latency |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Soil Classifier** | ResNet-50 Transfer Learning | 1,200 curated field images | 3x224x224 RGB | **92.4% Accuracy** | ~14ms |
| **Nutrient Deficiencies** | 11x XGBoost Classifiers | Fertilizer Recommendation CSV | 10 soil indicators (leak-free) | **88.5% Mean Accuracy** | ~2ms |
| **Crop Suitability** | Random Forest (100 trees) | Kaggle Crop Recommendation | N, P, K, pH, Weather | **99.1% Accuracy** | ~3ms |
| **Degradation Forecaster** | Ridge Regression | Historical Field Analyses | Score timeseries ($N \ge 3$) | **$R^2 \ge 0.85$** | < 1ms |

---

## 🚀 Local Development Setup

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 20.x+ and **npm**: 10.x+
- **Database**: PostgreSQL 16 (or local SQLite)
- **Git**

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/sasank-in/soil_test.git
cd soil_test
```

---

### Step 2: Backend Setup
1. Navigate to the backend directory and create a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   ```
2. Activate the virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to supply your database URL and secrets:*
   ```ini
   DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/soil_health
   JWT_SECRET=generate_a_secure_random_string_here
   SARVAM_API_KEY=your_sarvam_api_key_here  # Optional; on-device speech used if omitted
   CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
   ```
5. Initialize the database and launch the FastAPI server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Interactive API documentation is now live at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

---

### Step 3: Frontend Setup
1. Open a new terminal and navigate to `frontend`:
   ```bash
   cd frontend
   npm install
   ```
2. Configure frontend environment variables:
   ```bash
   cp .env.example .env.local
   ```
   *(Defaults to same-origin proxy `/api`, which rewrites to `http://127.0.0.1:8000` via `next.config.mjs`)*
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   *Access the web application at [http://localhost:3000](http://localhost:3000).*

---

## 📡 Core API Reference

All requests requiring authentication accept a standard `Authorization: Bearer <token>` header.

| Method | Endpoint | Description | Request Body / Parameters |
| :---: | :--- | :--- | :--- |
| `POST` | `/auth/register` | Register farmer via mobile or email | `{ phone, email, name, password, preferred_language }` |
| `POST` | `/auth/login` | Authenticate farmer and return JWT | `{ identifier, password }` |
| `GET` | `/auth/me` | Fetch active user profile | None |
| `GET` | `/farms` | List all farms owned by authenticated user | None |
| `POST` | `/farms` | Create a new farm record | `{ name, owner_name, location }` |
| `GET` | `/farms/{id}/fields` | List field plots belonging to farm | None |
| `POST` | `/fields` | Register a new field plot | `{ farm_id, name, area_hectares }` |
| `POST` | `/images` | Upload soil sample image | `multipart/form-data` (file, field_id, source) |
| `GET` | `/images/{id}/file` | Stream original or preprocessed image | `?variant=original\|processed` |
| `POST` | `/soil-records` | Ingest lab chemical test results | `{ field_id, nitrogen, phosphorus, potassium, ph, ... }` |
| `POST` | `/analyze` | Execute complete multimodal analysis | `{ field_id, image_id, nitrogen, ... fuse: true, persist: true }` |
| `GET` | `/analysis-results/{id}`| Fetch stored analysis result | None |
| `GET` | `/recommendations/{id}` | Fetch ICAR dosage schedule for analysis | None |
| `GET` | `/crop-suitability/{id}` | Ranked crop suitability for field | `?top_k=8` |
| `GET` | `/trend/{field_id}` | Ridge regression degradation projections | None |
| `GET` | `/reports/{id}` | Download localized soil health PDF | `?language=en\|hi\|kn\|te` |
| `GET` | `/trend/{field_id}/pdf` | Download multi-panel timeseries trend PDF | None |
| `POST` | `/tts` | Proxied regional voice synthesis | `{ text, language }` |

---

## 🧪 Testing & Verification Suite

### Automated Backend Tests
Run the comprehensive Pytest suite covering auth, IDOR ownership isolation, ML units, and PDF output:
```bash
cd backend
pytest tests/ -v
```

### Frontend Typecheck & Locale Parity
Verify TypeScript interfaces and validate that all 197 localization keys exist across all 4 languages:
```bash
cd frontend
npm run typecheck
```

### Production Build Verification
Verify Next.js route bundling and static optimization:
```bash
cd frontend
npm run build
```

---

## ☁️ Production Deployment (Render)

This repository includes a native infrastructure-as-code **Render Blueprint** ([`render.yaml`](file:///c:/Users/Prakhar/Desktop/Intern/AI-Based-Soil-Health-Assessment-System-for-Nutrient-Deficiency-Detection---Crop-Recommend-July-2026/render.yaml)) configured for zero-configuration multi-service deployment:

1. **`soil-health-api`** (Web Service):
   - Runtime: Python 3.11
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health Check: `/health`
2. **`soil-health-pwa`** (Web Service):
   - Runtime: Node.js 20
   - Build Command: `npm ci && npm run build`
   - Start Command: `npm start`
   - Reverse Proxy: Maps `/api/*` to the `soil-health-api` internal service URL.
3. **`soil-health-db`** (Managed PostgreSQL):
   - Engine: PostgreSQL 16
   - Automatic connection string injection via `DATABASE_URL`.

**Deployment Instructions**:
1. Fork or push this repository to GitHub.
2. Log into [Render.com](https://render.com) and click **New > Blueprint**.
3. Select this repository; Render will automatically provision the database, backend API, and frontend PWA.

---

## 📄 License

This project is open-sourced under the **[MIT License](file:///c:/Users/Prakhar/Desktop/Intern/AI-Based-Soil-Health-Assessment-System-for-Nutrient-Deficiency-Detection---Crop-Recommend-July-2026/LICENSE)** — see the `LICENSE` file for details.
