from dirty_data_factory.seeding import derive_rng


def test_same_seed_and_name_reproducible():
    a = derive_rng(42, "typos").sample(range(1000), 20)
    b = derive_rng(42, "typos").sample(range(1000), 20)
    assert a == b


def test_different_injector_names_diverge():
    a = derive_rng(42, "typos").sample(range(1000), 20)
    b = derive_rng(42, "missing_values").sample(range(1000), 20)
    assert a != b


def test_different_seeds_diverge():
    a = derive_rng(42, "typos").sample(range(1000), 20)
    b = derive_rng(43, "typos").sample(range(1000), 20)
    assert a != b
