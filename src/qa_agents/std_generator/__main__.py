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
    parser.add_argument("tag", help="Task tag (also used to name the output file)")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output .xlsx path (default: output/STD_<tag>.xlsx)",
    )
    parser.add_argument(
        "--outputs",
        choices=["both", "scenarios", "sql"],
        default="both",
        help="Which outputs to produce (default: both)",
    )
    parser.add_argument(
        "--whole-spec",
        action="store_true",
        help="Generate for the whole spec instead of a specific tag",
    )
    args = parser.parse_args()

    scenarios = args.outputs in ("both", "scenarios")
    sql = args.outputs in ("both", "sql")
    tag = None if args.whole_spec else args.tag
    output = args.output or f"output/STD_{args.tag}.xlsx"

    out = generate_std(args.spec, tag, output, scenarios=scenarios, sql=sql)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
