import argparse
import datetime
import glob
import os
import sys

import yaml

SKIPLINES = 1
SECTIONS = [
    ("feature", "Features"),
    ("enhancement", "Enhancements"),
    ("server", "Server"),
    ("task", "Task Library"),
    ("fix", "Fixes"),
    ("deprecation", "Deprecations"),
    ("breaking", "Breaking Changes"),
    ("contributor", "Contributors"),
]
DEDUPLICATE_SECTIONS = ["contributor"]

TEMPLATE = """
## {version} <Badge text="beta" type="success" />

Released on {date}.

{sections}
"""

REPO_DIR = os.path.abspath(os.path.dirname(__file__))
CHANGELOG_PATH = os.path.join(REPO_DIR, "CHANGELOG.md")
CHANGES_DIR = os.path.join(REPO_DIR, "changes")


def run(version, overwrite=False):
    change_files = sorted(glob.glob(os.path.join(CHANGES_DIR, "*.yaml")))
    change_files = [p for p in change_files if not p.endswith("EXAMPLE.yaml")]
    # Load changes
    changes = {s: [] for s, _ in SECTIONS}
    for path in change_files:
        with open(path) as f:
            data = yaml.safe_load(f)
            for k, v in data.items():
                if k in changes:
                    if isinstance(v, list) and all(isinstance(i, str) for i in v):
                        changes[k].extend(v)
                    else:
                        raise ValueError(f"invalid file {path}")
                else:
                    raise ValueError(f"invalid file {path}")

    # Build up subsections
    sections = []
    for name, header in SECTIONS:
        values = changes[name]
        if name in DEDUPLICATE_SECTIONS:
            values = sorted(set(values))
        if values:
            text = "\n".join("- %s" % v for v in values)
            sections.append(f"{header}\n\n{text}")

    # Build new release section
    date = "{dt:%B} {dt.day}, {dt:%Y}".format(dt=datetime.date.today())
    new = TEMPLATE.format(version=version, date=date, sections="\n\n".join(sections))

    # Insert new section in existing changelog
    with open(CHANGELOG_PATH) as f:
        existing = f.readlines()

    head = existing[:SKIPLINES]
    tail = existing[SKIPLINES:]

    def write(f):
        f.writelines(head)
        f.write(new)
        f.writelines(tail)

    # Output results
    if overwrite:
        with open(CHANGELOG_PATH, "w") as f:
            write(f)
        # Remove change files that were added
        for path in change_files:
            os.remove(path)
    else:
        write(sys.stdout)


def main():
    parser = argparse.ArgumentParser(description="Update the Prefect changelog")
    parser.add_argument(
        "version", help="The version number to name this release section"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="If set, will overwrite the existing changelog and clear the `changes` directory",
    )
    args = parser.parse_args()
    run(args.version, args.overwrite)


if __name__ == "__main__":
    main()
