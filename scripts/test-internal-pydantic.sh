versions=(3.12 3.9)
pydantic=("pydantic<2" "pydantic<3")

for version in "${versions[@]}"; do
    uv venv $version
    source $version/bin/activate
    uv pip install -e "../.[dev]"
    for pydantic_version in "${pydantic[@]}"; do
        echo "Testing Python $version with $pydantic_version"
        pyenv local $version
        uv pip install -U $pydantic_version
        python -m pytest ../tests/_internal/pydantic
    done
    deactivate
    rm -rf $version
done
