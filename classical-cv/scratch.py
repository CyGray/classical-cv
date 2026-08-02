import csv

with open('outputs/independence/hybrid/lsdb1_fixed/_raw_runs/run_1/comparisons.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

rows.sort(key=lambda x: float(x['lbph_distance']))
print('Top 8 Lowest LBPH Distance Impostor Pairs:')
for i, row in enumerate(rows[:8]):
    print(f"{i+1}. {row['query_identity']} vs {row['candidate_identity']} - {float(row['lbph_distance']):.4f}")

print('\nChecking images used...')
images = set(row['query_image_path'] for row in rows)
for img in sorted(images):
    print(img)
