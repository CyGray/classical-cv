import os
import sys
import shutil
import tarfile
import urllib.request
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

LFW_URL = "https://ndownloader.figshare.com/files/5976018"
LFW_TAR_PATH = DATA_DIR / "lfw.tgz"
LFW_EXTRACT_DIR = DATA_DIR / "lfw-dataset"

def python_exe() -> str:
    return os.environ.get("FACE_G3_PYTHON") or sys.executable

def download_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = min(100.0, read_so_far * 100 / total_size)
        sys.stdout.write(f"\rDownloading LFW: {percent:.2f}% ({read_so_far / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB)")
    else:
        sys.stdout.write(f"\rDownloading LFW: {read_so_far / (1024*1024):.2f} MB")
    sys.stdout.flush()

def count_subdirs(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())

def count_images_recursive(path: Path) -> int:
    if not path.is_dir():
        return 0
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sum(
        1
        for root, dirs, files in os.walk(path)
        for f in files
        if Path(f).suffix.lower() in img_exts
    )

def fix_junctions():
    print("\n[STEP 1] Validating and repairing directory junctions...")
    junctions = {
        "split_augmented41mods_lasalle": "augmented41mods",
        "split_augmented41mods_lfw": "split_augmented41mods",
        "split_lasalle": "split_backup_before_lfw_20260423_132556",
        "split_lfw": "split",
    }
    
    for name, target_sub in junctions.items():
        link_path = DATA_DIR / name
        target_path = DATA_DIR / target_sub

        # Check if junction/symlink exists or is broken
        if os.path.lexists(link_path):
            print(f"  - Removing existing directory entry/junction: {name}")
            try:
                if os.path.islink(link_path):
                    os.unlink(link_path)
                else:
                    os.rmdir(link_path)
            except Exception:
                if os.name == "nt":
                    subprocess.run(["cmd.exe", "/c", "rmdir", "/s", "/q", str(link_path)], check=False)
                else:
                    shutil.rmtree(link_path, ignore_errors=True)

        # Create junction (Windows) or symlink (POSIX: Linux/Termux/macOS)
        print(f"  - Creating junction: {name} -> {target_sub}")
        if os.name == "nt":
            res = subprocess.run(["cmd.exe", "/c", "mklink", "/j", str(link_path), str(target_path)], capture_output=True, text=True)
            ok = res.returncode == 0
            err = res.stderr.strip()
        else:
            try:
                os.symlink(target_path, link_path, target_is_directory=True)
                ok, err = True, ""
            except OSError as e:
                ok, err = False, str(e)

        if not ok:
            print(f"    [ERROR] Failed to create junction {name}: {err}")
        else:
            print(f"    [SUCCESS] Junction {name} created")

def setup_lasalle_lfs():
    print("\n[STEP 2] Verifying La Salle DB1 (processed & split) files from Git LFS...")
    processed_dir = DATA_DIR / "lasalle_db1_processed"
    split_backup_dir = DATA_DIR / "split_backup_before_lfw_20260423_132556"
    
    # 28 identities with 12 images each = 336 images
    processed_images = count_images_recursive(processed_dir)
    split_images = count_images_recursive(split_backup_dir)
    
    print(f"  - lasalle_db1_processed image count: {processed_images} / 336")
    print(f"  - split_backup_before_lfw image count: {split_images} / 336")
    
    # If missing or incomplete, pull using git lfs
    if processed_images < 336 or split_images < 336:
        print("  - Files are missing or incomplete. Pulling from Git LFS...")
        res = subprocess.run(["git", "lfs", "pull"], cwd=str(PROJECT_ROOT))
        if res.returncode == 0:
            print("  - Git LFS pull completed successfully.")
        else:
            print("  - [WARN] Git LFS pull returned non-zero code. Make sure you have pushed to remote.")
    else:
        print("  - La Salle DB1 processed and split files are complete!")

def setup_lfw():
    print("\n[STEP 3] Verifying LFW dataset...")
    # LFW has 5,749 identities in the standard dataset
    lfw_subdirs = count_subdirs(LFW_EXTRACT_DIR)
    print(f"  - LFW subdirectories found: {lfw_subdirs} / 5749")
    
    if lfw_subdirs < 5000:
        if LFW_EXTRACT_DIR.exists():
            print("  - LFW dataset is incomplete. Removing and replacing...")
            shutil.rmtree(LFW_EXTRACT_DIR)
            
        print(f"  - Downloading LFW dataset from {LFW_URL}...")
        try:
            urllib.request.urlretrieve(LFW_URL, LFW_TAR_PATH, download_progress)
            print("\n  - Extracting LFW dataset...")
            
            temp_extract_dir = DATA_DIR / "lfw_temp_extracted"
            temp_extract_dir.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(LFW_TAR_PATH, "r:gz") as tar:
                tar.extractall(path=temp_extract_dir)
                
            extracted_lfw = temp_extract_dir / "lfw"
            if extracted_lfw.exists():
                extracted_lfw.rename(LFW_EXTRACT_DIR)
                
            if LFW_TAR_PATH.exists():
                LFW_TAR_PATH.unlink()
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
                
            print(f"  - [SUCCESS] LFW dataset pulled successfully: {count_subdirs(LFW_EXTRACT_DIR)} directories.")
        except Exception as e:
            print(f"\n  - [ERROR] Failed to download or extract LFW: {e}")
            sys.exit(1)
    else:
        print("  - LFW dataset is complete!")

def run_augmentation(split_root: str, output_root: str, label: str, expected_min_images: int):
    py = python_exe()
    out_path = PROJECT_ROOT / output_root
    images_count = count_images_recursive(out_path)
    
    print(f"\n[STEP 4] Verifying augmentation for {label}...")
    print(f"  - Current augmented images count: {images_count} / {expected_min_images}")
    
    if images_count < expected_min_images:
        print(f"  - Augmentation is missing or incomplete. Starting augmentation process...")
        cmd = [
            py,
            str(PROJECT_ROOT / "scripts" / "augment_split_light_medium.py"),
            "--split-root", split_root,
            "--output-root", output_root,
            "--overwrite"
        ]
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if res.returncode == 0:
            print(f"  - [SUCCESS] Augmentation completed for {label}.")
        else:
            print(f"  - [ERROR] Augmentation failed for {label}.")
    else:
        print(f"  - Augmentation for {label} is complete and matches specifications!")

def main():
    # Step 1: Repair directory junctions
    fix_junctions()
    
    # Step 2: Make sure La Salle is pulled from LFS
    setup_lasalle_lfs()
    
    # Step 3: Make sure LFW is pulled
    setup_lfw()
    
    # Step 4: Run augmentations if incomplete
    # La Salle has 336 images. With 2 light + 2 medium = 1344 augmented images.
    run_augmentation(
        "data/split_lasalle", 
        "data/split_augmented41mods_lasalle_clean", 
        "La Salle DB1",
        1344
    )
    
    # LFW has 5,985 source split images. 2 light + 2 medium = 23,940 augmented images.
    run_augmentation(
        "data/split_lfw", 
        "data/split_augmented41mods_lfw", 
        "LFW Dataset",
        23940
    )
    
    print("\n[COMPLETE] Setup script finished successfully!")

if __name__ == "__main__":
    main()
