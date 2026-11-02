# Agro_Robot

Tier 1 V1: agricultural robot for coffee or tea in Uganda.

- Perception trained on public datasets (crop chosen by data audit)
- ROS 2 + Gazebo simulation on terrain derived from open DEM data
- Design constraints, kinematics and chassis concept

# Rules
- Datasets live on an external drive 

## 🗂️ Dataset Preparation & Auditing

We use the **Croppie Coffee Dataset** (`rgautroncgiar/croppie_coffee_ug`) for training our object detection model. However, before training, we performed a rigorous Exploratory Data Analysis (EDA) to ensure data quality.

### Why we audited the data:
1.  **Class Imbalance:** The original Mendeley dataset was dropped because 96% of its labels were for "Unripe" cherries.
2.  **Data Leakage:** The Croppie dataset originally had temporal data leakage (tiles from the same drone photo were split across both `train` and `val` folders).
3.  **Bounding Box Size:** We verified that the Croppie dataset features bounding boxes large enough (~48px) to survive YOLO's image resizing.

### 🛠️ The Scripts
We wrote custom Python scripts to audit and clean the data. You can find them in the `scripts/` folder:
*   `audit_batches.py`: Audits raw YOLO datasets for class imbalance, duplicates, and missing pairs.
*   `audit_croppie.py`: A specialized version of the audit for the Croppie dataset, checking for bounding box sizes and source-photo grouping.
*   `fix_split.py`: Merges the raw train/val folders and re-splits them chronologically by source timestamp to eliminate 100% of the data leakage.

### 🚀 How to Run the Scripts
*(Note: Replace `<path_to_dataset>` with your actual folder path).*

**1. Audit a standard dataset (Windows PowerShell):**
```powershell
python scripts/audit_batches.py "<path_to_dataset>" --names Unripe,Ripening,Ripe,Spoilt,Coffee_tree
