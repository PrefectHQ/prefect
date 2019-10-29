# Release Checklist

There are a few steps we need to take when cutting a new Prefect release; this document serves as a checklist for what needs to happen for a successful release:

- [ ] Update the [CHANGELOG.md](https://github.com/PrefectHQ/prefect/blob/master/CHANGELOG.md) section headers
- [ ] Optionally tag a release candidate _locally_ and [push to Test PyPI](https://packaging.python.org/tutorials/packaging-projects/#uploading-the-distribution-archives)
- [ ] [Draft a new release in GitHub](https://github.com/PrefectHQ/prefect/releases) - typically we try to name them and include the changelog in the notes
- [ ] Pull the new `git tag` locally, [rebuild the distribution archives](https://packaging.python.org/tutorials/packaging-projects/#generating-distribution-archives) and use `twine upload dist/*` to upload to PyPI
- [ ] Pushing to PyPI should trigger a PR to the [`prefect-feedstock` conda-forge repo](https://github.com/conda-forge/prefect-feedstock) (although it could take hours); upon approval and merge, this will land the new release in `conda-forge` as well.  Alternatively, you can open a PR yourself to get the ball rolling
- [ ] Lastly, [archive the new tagged release API documentation](documentation.html#archiving-api-docs)

That's it!
