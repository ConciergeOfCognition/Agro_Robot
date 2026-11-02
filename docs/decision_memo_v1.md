# Tier 1 V1 Decision Memo: Crop and Task

**Date:** October 2026
**Author:** Agro_Robot Team
**Status:** Approved for V1

## 1. The Decision
After completing a rigorous Exploratory Data Analysis (EDA) on public datasets, we have decided to proceed with **Coffee** as our target crop and **Coffee Cherry Ripeness Detection** as our primary machine learning task. 

## 2. Task Definition
*   **Task Type:** Object Detection (YOLO format).
*   **Classes:** 5 (Dark Brown, Green, Low Visibility/Unsure, Red, Yellow).
*   **Robot Goal:** Detect the bounding boxes for ripe (Red) and unripe (Green) cherries to inform harvesting/navigation.

## 3. Dataset Selection & Justification
We audited two primary datasets:
1.  **Mendeley (Mak-AI):** Dropped. While it had real Ugandan drone images, it suffered from a 96% class imbalance (mostly unripe) and tiny bounding boxes (~24px) that would be lost during standard YOLO resizing.
2.  **Croppie (`rgautroncgiar/croppie_coffee_ug`):** Selected. This dataset features a near-perfect 50/50 class balance for ripeness, an image size of 480x640, and median bounding boxes of ~48px. 

## 4. Data Cleaning & Risks
**Data Leakage Resolved:** The Croppie dataset originally suffered from temporal data leakage (tiles from the same source photo were split between train and val). We wrote a Python script to group images by their source timestamp and re-split them chronologically (80/20). The dataset is now verified to have 0% leakage.

## 5. Hardware & Training Plan
*   **Local Hardware:** Intel MacBook Pro (No local CUDA GPU).
*   **Training Environment:** Google Colab (Free Tier).
*   **Model:** YOLOv8n (Nano) or YOLOv8s (Small) - chosen for fast inference latency on robotics hardware, and because the original dataset authors used YOLOv8.
*   **Image Size:** 640x640.

## 6. Next Milestones
1.  Train baseline model on Colab.
2.  Extract `.pt` weights and test inference on unseen images.
3.  Integrate the trained model into the Gazebo simulation pipeline.
