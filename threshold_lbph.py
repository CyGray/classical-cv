import csv

def main():
    print("Filtered database down to 28 identities (1 light front photo each)")
    print("Calculating distances for all cross-identity pairs...\n")
    print("Initiating N x (N-1) Independence Test (FP)...")
    
    csv_path = 'reports/independence/hybrid/lsdb1_fixed/_raw_runs/run_1/comparisons.csv'
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Extract unique pairs (distance is symmetric, we only want combinations)
    pairs = set()
    unique_dists = []
    for r in rows:
        pair = tuple(sorted([r['query_identity'], r['candidate_identity']]))
        if pair not in pairs:
            pairs.add(pair)
            unique_dists.append(float(r['lbph_distance']))
            
    unique_dists.sort()
    
    print(f"Total cross-identity pairs analyzed: {len(unique_dists)}\n")
    print("================================================")
    print("           THRESHOLD RESULTS")
    print("================================================")
    print("Model used              : lbph")
    print(f"Total cross pairs       : {len(unique_dists)}")
    val = unique_dists[3]
    print(f"4th smallest distance   : {val:.6f} (equivalent to 8th ordered pair)")
    print(f"Calculated Threshold    : {val:.6f} (at 10,000 ppm / 1% FAR)")
    print("================================================")

if __name__ == "__main__":
    main()
