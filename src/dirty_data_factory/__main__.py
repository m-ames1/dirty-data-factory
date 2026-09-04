"""CLI entry point: python -m dirty_data_factory [options]"""

import argparse
import dataclasses
from pathlib import Path

from dirty_data_factory.config import load_config
from dirty_data_factory.pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dirty_data_factory")
    parser.add_argument(
        "--config", type=Path, default=Path("injection_config.toml"), help="path to the TOML config"
    )
    parser.add_argument("--seed", type=int, default=None, help="override run.seed from the config")
    parser.add_argument("--input", type=Path, default=None, help="override the input CSV directory")
    parser.add_argument("--output", type=Path, default=None, help="override the output directory")
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    config = load_config(args.config, repo_root=repo_root)

    overrides = {}
    if args.seed is not None:
        overrides["seed"] = args.seed
    if args.input is not None:
        overrides["input_dir"] = args.input
    if args.output is not None:
        overrides["output_dir"] = args.output
    if overrides:
        config = dataclasses.replace(config, **overrides)

    result = run(config)
    print(f"Wrote dirty output to {config.output_dir}")
    print(f"Manifest: {result.manifest_path}")
    print(f"Total injected changes: {sum(result.change_counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
