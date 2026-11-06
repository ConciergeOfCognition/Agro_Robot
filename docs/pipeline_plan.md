# ML Pipeline Plan: Coffee Cherry Detection

## 1. Data Preparation
- **Dataset 1 (Training):** Croppie (Uganda). Cleaned and split (80/20) to remove data leakage.
- **Dataset 2 (Testing):** Kaggle Coffee Cherry (Indonesia). Audited for quality; labels mapped to Croppie classes.

## 2. Model Training (Baseline)
- **Architecture:** YOLOv8n (Nano).
- **Environment:** Google Colab (T4 GPU).
- **Hyperparameters:** 50 epochs, image size 640, batch 16, `max_det=500`.
- **Output:** `best.pt` weights saved to Google Drive.

## 3. Baseline Evaluation
- **Metrics:** mAP50, mAP50-95, Precision, Recall.
- **Error Analysis:** Custom script to evaluate recall by bounding box size (revealed drops in accuracy for <16px objects).
- **Findings:** High accuracy on red cherries, but poor performance on the underrepresented `low_visibility` class.

## 4. Cross-Dataset Evaluation (Domain Gap)
- **Conversion:** Map Dataset 2 labels into Dataset 1 class IDs.
- **Inference:** Run `best.pt` on Dataset 2 images.
- **Goal:** Measure mAP drop to quantify the domain gap between drone imagery (Croppie) and close-up photography (Kaggle).

## 5. Next Steps (Post-Gate 1)
- Model improvement (e.g., YOLOv8s, higher resolution).
- Integrate model into ROS 2 simulation environment.
