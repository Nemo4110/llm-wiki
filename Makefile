# LLM-Wiki Release Makefile
# Usage: make release [VERSION=x.y.z]

# Extract version from SKILL.md. Override with `make release VERSION=x.y.z`.
PY ?= python
VERSION := $(shell $(PY) scripts/create_release.py --print-version)

# Paths
RELEASE_DIR := release
PACKAGE_NAME := llm-wiki-v$(VERSION)
PACKAGE_DIR := $(RELEASE_DIR)/$(PACKAGE_NAME)
ZIP_FILE := $(RELEASE_DIR)/$(PACKAGE_NAME).zip

.PHONY: help check list release clean

# Show help
help:
	@echo "LLM-Wiki Release Manager"
	@echo ""
	@echo "Available commands:"
	@echo "  make check       - Show current version"
	@echo "  make list        - List all releases"
	@echo "  make release     - Create release package"
	@echo "  make clean       - Remove all releases"
	@echo ""

# Check current version
check:
	@echo "Current version: $(VERSION)"
	@echo "Package name: $(PACKAGE_NAME)"
	@echo "Zip file: $(ZIP_FILE)"

# List releases
list:
	@echo "Available releases:"
	@ls -1 $(RELEASE_DIR) 2>/dev/null || echo "  (none)"

# Create release package
release:
	@$(PY) scripts/create_release.py $(VERSION)
	@echo ""
	@echo "Next steps:"
	@echo "  1. Archive: $(ZIP_FILE)"
	@echo "  2. Upload to Clawhub"
	@echo "  3. git tag v$(VERSION) && git push origin v$(VERSION)"

# Clean all releases
clean:
	@$(PY) -c "import shutil; shutil.rmtree('$(RELEASE_DIR)', ignore_errors=True)"
	@echo "All releases cleaned"
