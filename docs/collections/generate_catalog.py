"""Script to generate the collections catalog table"""
import mkdocs_gen_files
import yaml
import glob
from pathlib import Path

ITEMS_IN_ROW = 3

with mkdocs_gen_files.open("collections/catalog.md", "a") as markdown_file:
    collection_files = [
        file
        for file in glob.glob("./docs/collections/catalog/*.yaml")
        if Path(file).name != "TEMPLATE.yaml"
    ]

    collection_configs = []
    for collection_file in collection_files:
        with open(collection_file, "r") as file:
            collection_configs.append(yaml.safe_load(file))

    # TODO: Remove. For testing.
    collection_configs = collection_configs * 8

    chunked_collection_configs = [
        collection_configs[i : i + ITEMS_IN_ROW]
        for i in range(0, len(collection_configs), ITEMS_IN_ROW)
    ]

    print("<table>", file=markdown_file)
    for row in chunked_collection_configs:
        print("<tr>", file=markdown_file)
        for item in row:
            print(f"""
            <td>
                <h4>{item['collectionName']}</h4>
                <img src={item['iconUrl']} style="max-height: 128px; max-width: 128px">
            </td>
            """, file=markdown_file)
        print("</tr>", file=markdown_file)
    print("</table>", file=markdown_file)
