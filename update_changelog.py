import argparse
import datetime
import glob
import os

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

TEMPLATE = """\
## {version} <Badge text="beta" type="success" />

Released on {date}.

{sections}
"""

REPO_DIR = os.path.abspath(os.path.dirname(__file__))
CHANGELOG_PATH = os.path.join(REPO_DIR, "CHANGELOG.md")
CHANGES_DIR = os.path.join(REPO_DIR, "changes")


def get_change_files():
    change_files = sorted(glob.glob(os.path.join(CHANGES_DIR, "*.yaml")))
    change_files = [p for p in change_files if not p.endswith("EXAMPLE.yaml")]
    return change_files


def generate_new_section(version):
    # Load changes
    changes = {s: [] for s, _ in SECTIONS}
    for path in get_change_files():
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
            sections.append(f"### {header}\n\n{text}")

    # Build new release section
    date = "{dt:%B} {dt.day}, {dt:%Y}".format(dt=datetime.date.today())
    return TEMPLATE.format(version=version, date=date, sections="\n\n".join(sections))


def preview():
    print(generate_new_section("Upcoming Release"))


def generate(version):
    new = generate_new_section(version)
    # Insert new section in existing changelog
    with open(CHANGELOG_PATH) as f:
        existing = f.readlines()

    head = existing[:SKIPLINES]
    tail = existing[SKIPLINES:]

    with open(CHANGELOG_PATH, "w") as f:
        f.writelines(head)
        f.write("\n")
        f.write(new)
        f.writelines(tail)
    # Remove change files that were added
    for path in get_change_files():
        os.remove(path)


def main():
    parser = argparse.ArgumentParser(description="Update the Prefect changelog")
    subparser = parser.add_subparsers(metavar="command", dest="command")
    subparser.required = True
    preview_parser = subparser.add_parser(
        "preview", help="Preview just the new section of of the changelog"
    )
    preview_parser.set_defaults(command="preview")
    generate_parser = subparser.add_parser(
        "generate",
        help="Generate the changelog for a release, and cleanup the `changes` directory",
    )
    generate_parser.set_defaults(command="generate")
    generate_parser.add_argument(
        "version", help="The version number to name this release section"
    )
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.version)
    elif args.command == "preview":
        preview()


if __name__ == "__main__":
    main()
