from pathlib import Path
from typing import Generator


def docs_path() -> Path:
    return Path(__file__).parent.parent / "docs"


SKIPPED = [
    "prefect._internal",
    "prefect.server.database.migrations",
]


def main():
    for package, path in packages():
        module = package.replace("-", "_")

        modules = []
        for python_file in (path / module).rglob("**/*.py"):
            if python_file.name.startswith("_") and python_file.name != "__init__.py":
                continue

            submodule = str(python_file.relative_to(path).with_suffix(""))
            submodule = submodule.replace("/", ".")
            if any(submodule.startswith(skipped) for skipped in SKIPPED):
                continue
            modules.append(submodule)

        package_docs = docs_path() / "sdk"

        for module in sorted(modules):
            module_name = module.replace(".__init__", "")
            doc_filename = module.replace(".", "/").replace("__init__", "index")
            module_file = (package_docs / doc_filename).with_suffix(".md")
            module_file.parent.mkdir(parents=True, exist_ok=True)
            with open(module_file, "w") as file:
                file.write(f"# {module_name}\n\n")
                file.write(f"::: {module_name}\n")

        break


def packages() -> Generator[tuple[str, Path], None, None]:
    yield "prefect", Path("./src")

    for path in sorted(Path("./src/integrations").iterdir()):
        if path.is_dir():
            yield path.name, path


if __name__ == "__main__":
    main()
