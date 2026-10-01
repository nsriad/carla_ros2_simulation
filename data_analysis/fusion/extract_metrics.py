import os
import glob
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_dir", default="../data/multimodal_dataset_20260713_191320", help="Directory containing the processed_fusion_* folders")
    args = parser.parse_args()

    report_name = "mlp_mse_nodiff_fused_report.txt"
    search_pattern = os.path.join(args.base_dir, "processed_fusion_*", report_name)
    report_files = glob.glob(search_pattern)

    data = []

    for file_path in report_files:
        # Extract the condition name from the folder (e.g., 'processed_fusion_cam_drop' -> 'cam_drop')
        folder_name = os.path.basename(os.path.dirname(file_path))
        condition = folder_name.replace("processed_fusion_", "")
        
        row = {"Condition": condition}
        
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.split()
                # Ensure the line has enough columns to contain MAE and RMSE
                if len(parts) >= 3:
                    if "LiDAR alone" in line:
                        row["LiDAR_MAE"] = float(parts[-2])
                        row["LiDAR_RMSE"] = float(parts[-1])
                    elif "Camera alone" in line:
                        row["Camera_MAE"] = float(parts[-2])
                        row["Camera_RMSE"] = float(parts[-1])
                    elif "mlp_mse_nodiff_fused" in line:
                        row["Fused_MAE"] = float(parts[-2])
                        row["Fused_RMSE"] = float(parts[-1])
        
        data.append(row)

    # Compile and save
    df = pd.DataFrame(data)
    output_csv = os.path.join(args.base_dir, "compiled_ablation_results.csv")
    df.to_csv(output_csv, index=False)
    
    print(f"Successfully compiled {len(data)} reports into {output_csv}")

if __name__ == "__main__":
    main()
