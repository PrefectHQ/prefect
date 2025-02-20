import os
import re


def convert_md_to_mdx(input_file, output_file):
    with (
        open(input_file, "r", encoding="utf-8") as infile,
        open(output_file, "w", encoding="utf-8") as outfile,
    ):
        # Read the entire content of the file
        content = infile.read()

        # Remove everything from "## Table of Contents" to the next second-level header
        content = re.sub(r"(?s)## Table of Contents.*?(?=\n## )", "", content)

        # Convert <url> to [url](url)
        content = re.sub(r"<(http[s]?://[^>]+)>", r"[\1](\1)", content)

        # Remove bold and italic markers
        content = re.sub(r"\*\*", "", content)  # Remove bold markers
        content = re.sub(r"\*", "", content)  # Remove italic markers

        # Convert simple HTML tags to markdown
        content = re.sub(r"<b>(.*?)</b>", r"**\1**", content)
        content = re.sub(r"<i>(.*?)</i>", r"*\1*", content)
        content = re.sub(r"<strong>(.*?)</strong>", r"**\1**", content)
        content = re.sub(r"<em>(.*?)</em>", r"*\1*", content)

        # Ensure code blocks are fenced and keep language identifier on the same line
        content = re.sub(r"```(\w+)?\n```", r"```\1", content)

        # Convert HTML image tags to markdown image syntax
        content = re.sub(r'<img src="([^"]+)" alt="([^"]*)">', r"![\2](\1)", content)

        # Double escape curly braces
        content = content.replace("{", "\\{").replace("}", "\\}")

        # Escape single HTML tags
        content = re.sub(r"<(\w+)>", r"&lt;\1&gt;", content)

        # Write the processed content to the output file
        outfile.write(content)
        # remove .md file
        os.remove(input_file)


def process_directory(directory):
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            input_file = os.path.join(directory, filename)
            output_file = os.path.join(directory, filename.replace(".md", ".mdx"))
            convert_md_to_mdx(input_file, output_file)
            print(f"Converted {input_file} to {output_file}")


if __name__ == "__main__":
    process_directory("../docs/v3/api-ref/python")
