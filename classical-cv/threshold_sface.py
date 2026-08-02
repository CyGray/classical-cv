import os
import numpy as np
import cv2 as cv
from src.sface.recognizer import SFaceRecognizer

def main():
    print("Filtered database down to 28 identities (1 light front photo each)")
    print("Calculating distances for all cross-identity pairs...\n")
    print("Initiating N x (N-1) Independence Test (FP)...")
    
    dataset_dir = "data/lasalle_db1_processed"
    people = sorted(os.listdir(dataset_dir))
    
    sface = SFaceRecognizer()
    
    feats = []
    for person in people:
        path = os.path.join(dataset_dir, person, "light_front.jpg")
        image_bgr = cv.imread(path)
        # Using feature_from_crop since the processed DB already has crops
        feature = sface.feature_from_crop(image_bgr)
        feats.append(np.asarray(feature, dtype=np.float32).reshape(1, -1))
        
    feats = np.concatenate(feats, axis=0)
    norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)
    cos = (norm @ norm.T).astype(np.float32)
    l2 = np.sqrt(np.clip(2.0 - 2.0 * cos, 0.0, None))
    
    n = len(people)
    unique_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            unique_pairs.append(float(l2[i, j]))
            
    unique_pairs.sort()
    
    print(f"Total cross-identity pairs analyzed: {len(unique_pairs)}\n")
    print("================================================")
    print("           THRESHOLD RESULTS")
    print("================================================")
    print("Model used              : sface")
    print(f"Total cross pairs       : {len(unique_pairs)}")
    val = unique_pairs[7]
    print(f"8th smallest distance   : {val:.6f}")
    print(f"Calculated Threshold    : {val:.6f} (at 10,000 ppm / 1% FAR)")
    print("================================================")

if __name__ == "__main__":
    main()
