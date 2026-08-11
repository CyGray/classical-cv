# Changelog - 2026-04-21

## Summary
Updated the train/eval split path with light + medium augment coverage and ran FPS sanity sessions after rerunning all models.

## 1) Data split and augmentation flow
- Added light and medium modified variants to train/eval split handling for broader generalization.
- Pointed defaults and argument wiring to the split + augmented split flow (raw remains explicit, not default) for consistency.

## 2) Full retrain and re-eval
- Retrained and re-evaluated all models with:
  - Training: `processed + light + medium`
  - Testing: `processed` split (no augmentation)

## 3) Runtime performance pass
- Ran 60-second sessions per model to record average FPS on the refreshed setup.
