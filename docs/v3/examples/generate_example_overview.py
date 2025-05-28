import glob
import os
import re


def get_all_mdx_files() -> list[str]:
    files = glob.glob("*.mdx")
    return [f for f in files if f != "index.mdx"]


def generate_cards(files: list[str]) -> str:
    body = """<CardGroup cols={3}>\n"""

    for file in files:
        path, _ = file.split(".mdx")
        with open(file, "r") as f:
            text = f.read()

        pattern = r"title:\s*(.+)\ndescription:\s*(.+)"
        match = re.search(pattern, text)

        if not match:
            raise ValueError(f"File {file} does not have a title or description")

        title = match.group(1)
        description = match.group(2)

        body += f"""
          <Card title="{title}" icon="play" href="/v3/examples/{path}">
            {description}
          </Card>\n
          """
    body += """</CardGroup>\n"""
    return body


def main():
    files = get_all_mdx_files()
    print(files)
    card_table = generate_cards(files)
    with open("index.mdx", "w") as f:
        f.write("""---\ntitle: Examples\n---\n""")
        f.write(card_table)

if __name__ == "__main__":
    main()
