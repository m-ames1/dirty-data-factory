"""Per-injector RNG derivation so adding one injector never perturbs another's draws."""

import hashlib
import random


def derive_rng(top_seed: int, injector_name: str) -> random.Random:
    digest = hashlib.sha256(f"{top_seed}:{injector_name}".encode()).digest()
    sub_seed = int.from_bytes(digest[:8], byteorder="big")
    return random.Random(sub_seed)
