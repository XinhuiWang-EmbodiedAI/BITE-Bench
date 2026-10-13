"""Seed the installed CPU numerical stack."""

import random

import numpy as np


def seed_cpu(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
