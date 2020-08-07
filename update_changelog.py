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
    change_files.extend(sorted(glob.glob(os.path.join(CHANGES_DIR, "*.yml"))))
    change_files = [p for p in change_files if not p.endswith("EXAMPLE.yaml")]
    return change_files


def bad_entry(path):
    return ValueError(
        f"{path!r} does not contain a valid changelog entry, see the "
        f"`changes/README.md` file for more information."
    )


def generate_new_section(version):
    # Load changes
    changes = {s: [] for s, _ in SECTIONS}
    for path in get_change_files():
        with open(path) as f:
            try:
                data = yaml.safe_load(f)
            except Exception:
                raise ValueError(
                    f"{path!r} does not contain valid YAML - perhaps you forgot to quote a string?"
                )
            if not isinstance(data, dict):
                raise bad_entry(path)
            for k, v in data.items():
                if k in changes:
                    if isinstance(v, list) and all(isinstance(i, str) for i in v):
                        changes[k].extend(v)
                    else:
                        raise bad_entry(path)
                else:
                    raise bad_entry(path)

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


def lint():
    try:
        generate_new_section("Upcoming Release")
    except Exception as exc:
        print("Linting the `changes/` directory failed:\n")
        print(exc)
        sys.exit(1)
    else:
        print("All `changes/` files are in excellent condition!")


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
    lint_parser = subparser.add_parser(
        "lint", help="Ensure the changelog entries are all valid"
    )
    lint_parser.set_defaults(command="lint")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.version)
    elif args.command == "preview":
        preview()
    elif args.command == "lint":
        lint()


if __name__ == "__main__":
    main()
