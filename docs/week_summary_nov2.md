# Week Summary (Nov 2 - Nov 6)

## What Worked
*   Successfully trained the YOLOv8n baseline model on the Croppie dataset via Google Colab.
*   Achieved a baseline mAP50 of 0.590 (59%).
*   Error analysis completed: The model is excellent at finding large/red cherries (90% recall) but struggles with tiny objects (<16px, 65% recall) and the underrepresented `low_visibility_unsure` class.
*   Dataset 2 (Kaggle Coffee Cherry) was audited, verified, and class mapping was created.

## What Blocked Us
*   **Colab I/O Limits:** Training crashed when reading directly from Google Drive. Fixed by copying the dataset to Colab's local SSD.
*   **Colab GPU Memory:** Custom evaluation scripts crashed the GPU (OOM). Fixed by batching predictions one-by-one and forcing CPU execution for math-heavy scripts.
*   **Dataset 2 Hurdle:** The original CIRAD dataset had no ripeness labels. Pivoted to the Kaggle dataset.

## Decisions Needed
*   **Drop `low_visibility_unsure`:** The class only had 619 instances and achieved 0% recall. We should drop it for the v1 MVP to improve overall precision.
*   **Deployment Threshold:** Set the robot's confidence threshold to 0.306 (based on the F1-curve). 

## Next Steps (W3-W4)
*   Run Cross-Dataset Test (Kaggle) to measure domain gap.
*   Pivot to ROS 2 / Gazebo simulation (URDF, teleop, Nav2).
