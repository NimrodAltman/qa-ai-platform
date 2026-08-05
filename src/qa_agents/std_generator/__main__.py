"""Command-line entry point.

    python -m qa_agents.std_generator <spec-file> <task-tag> <output.xlsx>

Requires ANTHROPIC_API_KEY in the environment for a real run.
"""

from __future__ import annotations

import argparse

from .pipeline import generate_std


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qa_agents.std_generator",
        description="Generate an STD (test scenarios + SQL) from a specification.",
    )
    parser.add_argument("spec", help="Path to the specification (.docx / .xlsx / .pdf)")
    parser.add_argument("tag", help="Task tag to generate scenarios for")
    parser.add_argument("output", help="Output .xlsx path")
    args = parser.parse_args()

    out = generate_std(args.spec, args.tag, args.output)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
