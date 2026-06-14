You are GPT-5.3 Codex working inside my existing Python computer vision project.

Goal:
Add an LBPH independence test workflow under /src/lbph, then expose it as a separate CLI menu item in main.py.

Context:
This project already has Python scripts for training and testing classical face recognition models such as LBPH, Fisherfaces, and Eigenfaces. For the current project requirement, we need to perform an independence test for LBPH.

The independence test is different from normal train/test accuracy. It checks the false positive behavior and distance distribution between different identities.

Project requirement from our presentation:
- Algorithm to check: LBPH
- Dataset: La Salle DB 1
- Use 28 images, 1 image per person
- Perform N × (N - 1) comparisons excluding self-comparison
- For N = 28, expected comparison count is 28 × 27 = 756
- Check distance values
- Perform statistical processing:
  - distance range
  - frequency distribution
  - minimum distance
  - maximum distance
  - mean distance
  - median distance
  - standard deviation
  - possible threshold suggestion
- Purpose:
  - check false positive rate
  - understand the distance distribution
  - help decide recognition threshold
  - evaluate whether LBPH feature vectors are discriminative enough

Important:
This is NOT the same as training data = test data recognition checking.
This independence test must compare different people only.
Do not compare an image with itself.
Do not compare images from the same identity unless there is only one selected image per identity.
The expected first-step setup is one image per person, so all comparisons should be cross-identity.

Your task:
1. Inspect the existing project structure.
2. Inspect main.py and the existing /src/lbph files.
3. Reuse existing dataset loading, preprocessing, face extraction, label mapping, and LBPH helper functions where possible.
4. Add the minimum necessary new files/scripts under /src/lbph.
5. Add a separate CLI menu item in main.py for:
   "LBPH Independence Test"
6. Make the new CLI item run the independence test cleanly.

Implementation requirements:

A. New LBPH independence test script
Create a new module under /src/lbph, for example:

src/lbph/independence_test.py

The script should provide a callable function that main.py can import and run, such as:

run_lbph_independence_test()

or, if the existing project uses a different naming style, follow the existing style.

B. Dataset selection
The independence test should support selecting or configuring:
- dataset root path
- output path
- one-image-per-person mode

If the project already has standard dataset paths or CLI input style, follow that existing convention.

The independence test must select exactly one valid image per identity/person folder.

Selection rule:
- Default: use the first valid image after sorting filenames alphabetically.
- Also allow random selection with a fixed seed if simple to add.
- Make the selected image list visible in the output summary.

C. Preprocessing
Use the same preprocessing pipeline currently used by LBPH training/testing if possible.

Important:
Do not create a separate incompatible preprocessing pipeline unless necessary.

If existing helpers are available, reuse them:
- face detection
- crop extraction
- grayscale conversion
- resize
- normalization
- label inference
- dataset traversal

If a face cannot be detected or processed:
- skip that image
- log the skipped file and reason
- continue running
- warn if fewer than 2 identities remain

D. LBPH model behavior
For independence testing, train the LBPH recognizer using the selected one-image-per-person dataset.

Then compare each selected image against the model while excluding its own identity.

Since OpenCV LBPH predict() returns only the nearest identity and distance, implement pairwise comparison in a way that supports cross-identity distance collection.

Preferred approach:
- Train one LBPH model per identity/image, or use LBPH histogram extraction if available.
- If the existing code can extract LBPH histograms directly, compute pairwise distances between histograms.
- If using OpenCV face recognizer directly, carefully design the comparison so that the distance between each query and each other identity can be collected.

The output must include all ordered cross-identity comparisons:
N × (N - 1)

For 28 selected identities, this should produce 756 comparisons.

Each comparison record should include:
- query_identity
- query_image_path
- candidate_identity
- candidate_image_path
- distance
- is_false_positive_at_threshold if threshold is provided

E. Threshold and false positive rate
Allow the test to run with an optional threshold.

If threshold is provided:
- count comparison as false positive when distance <= threshold
- compute false positive count
- compute false positive rate = false_positive_count / total_comparisons

If no threshold is provided:
- still compute statistics
- suggest possible thresholds based on distance percentiles

Suggested threshold output:
- 1st percentile
- 5th percentile
- 10th percentile
- minimum distance
- mean minus 1 standard deviation, if meaningful

Make it clear that suggested thresholds are exploratory, not final.

F. Statistical output
Print a readable console report containing:

LBPH Independence Test Report

Dataset:
- dataset path
- total identities discovered
- identities selected
- selected images
- skipped images

Comparison Summary:
- expected comparisons: N × (N - 1)
- actual comparisons
- whether actual count matches expected count

Distance Statistics:
- min
- max
- mean
- median
- standard deviation
- percentiles: 1%, 5%, 10%, 25%, 50%, 75%, 90%, 95%, 99%

Threshold / False Positive Summary:
- threshold used, if any
- false positive count
- false positive rate

Closest Cross-Identity Matches:
- show top 10 lowest-distance comparisons
- include query identity, candidate identity, distance, and image paths

G. Output files
Save results under an output directory, for example:

outputs/lbph/independence_test/

Generate:
1. CSV file with all pairwise comparison records
2. JSON summary file with dataset info, statistics, threshold info, and top closest matches
3. Optional histogram image if matplotlib is already used in the project

Do not add heavy new dependencies.
Allowed:
- standard library
- numpy
- pandas only if already used
- matplotlib only if already used
- cv2/OpenCV, already required by the project

If pandas is not already used, use csv from the standard library.

H. CLI integration
Modify main.py to add a separate menu item:

LBPH Independence Test

Follow the existing main.py CLI style.
Do not rewrite the whole launcher.
Do not break existing menu options.
Do not renumber carelessly if the launcher depends on numeric choices.

The menu item should ask for:
- dataset path, or use default if project has one
- output directory, or use default
- optional threshold, blank means none
- optional random seed / selection mode only if easy and clean

Then call the independence test function.

I. Code quality requirements
- Keep code readable and modular.
- Add type hints where consistent with the existing project.
- Handle errors gracefully.
- Avoid global side effects.
- Keep output paths cross-platform using pathlib.
- Avoid hardcoded absolute paths.
- Do not remove or rename existing functions unless necessary.
- Do not change behavior of existing train/test scripts.
- Do not add unrelated features.

J. Validation
After implementation:
1. Run or inspect the project enough to verify imports work.
2. Run the new CLI path if possible.
3. Verify that for 28 selected identities, actual comparisons = 756.
4. Verify output CSV and JSON are created.
5. Check for syntax errors.
6. Summarize exactly what files were added or changed.

K. Final response format
After editing, respond with:

Implemented:
- list of added files
- list of modified files

How to run:
- exact command or CLI path

Output:
- expected output folder
- generated files

Validation:
- what checks passed
- any assumptions or limitations

Do not include unnecessary commentary.
Do not rewrite unrelated parts of the project.