"Copies README.md to index.md."

from pathlib import Path

import mkdocs_gen_files

readme_path = Path("README.md")
docs_index_path = Path("index.md")

with open(readme_path, "r") as readme:
    with mkdocs_gen_files.open(docs_index_path, "w") as generated_file:
        for line in readme:
            generated_file.write(line)

    mkdocs_gen_files.set_edit_path(Path(docs_index_path), readme_path)
