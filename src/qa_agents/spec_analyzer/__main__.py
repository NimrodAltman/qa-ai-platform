"""Command-line entry point.

    python -m qa_agents.spec_analyzer <spec-file> [tag] [output.docx]

Requires ANTHROPIC_API_KEY in the environment for a real run.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from .pipeline import default_output_name, generate_analysis


def main() -> None:
    load_dotenv()  # pick up ANTHROPIC_API_KEY and optional QA_MODEL from .env

    parser = argparse.ArgumentParser(
        prog="qa_agents.spec_analyzer",
        description="Analyze a specification's readiness before testing begins.",
    )
    parser.add_argument("spec", help="Path to the specification (.docx / .xlsx / .pdf)")
    parser.add_argument(
        "tag",
        nargs="?",
        default=None,
        help="Optional task tag to focus the analysis on (default: whole spec)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output .docx path (default: output/ANALYSIS_<tag-or-full_spec>.docx)",
    )
    args = parser.parse_args()

    output = args.output or default_output_name(args.tag or "full_spec")
    out = generate_analysis(args.spec, args.tag, output)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
