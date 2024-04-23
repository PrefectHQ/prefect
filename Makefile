.PHONY: docs

docs:
	@if [ ! -x "./scripts/serve_docs" ]; then \
		echo "Error: The 'serve_docs' script is not executable."; \
		echo "Please make it executable by running:"; \
		echo "  chmod +x \"./scripts/serve_docs\""; \
		echo "Then, run 'make docs' again."; \
		exit 1; \
	fi
	@./scripts/serve_docs