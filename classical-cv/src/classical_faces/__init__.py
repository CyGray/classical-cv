"""Shared backbone for the classical face-recognition track (LBPH / Eigenfaces / Fisherfaces).

All three pipelines import their preprocessing, dataset gathering, and the
train/evaluate engine from this package so they cannot drift apart again.
"""
