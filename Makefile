# LLM-Wiki Release Makefile
# Usage: make release [VERSION=x.y.z]

# Extract version from SKILL.md
VERSION := $(shell grep "^version:" SKILL.md 2>/dev/null | sed 's/version: *//' | tr -d '"' || echo "1.0.0")

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
	@echo "Creating release $(VERSION)..."
	@rm -rf $(PACKAGE_DIR) $(ZIP_FILE)
	@mkdir -p $(PACKAGE_DIR)/wiki $(PACKAGE_DIR)/sources

	@echo "Copying files..."
	@cp -r assets $(PACKAGE_DIR)/
	@cp -r docs $(PACKAGE_DIR)/
	@cp -r examples $(PACKAGE_DIR)/
	@cp -r hooks $(PACKAGE_DIR)/
	@cp -r scripts $(PACKAGE_DIR)/
	@cp -r src $(PACKAGE_DIR)/
	@echo "Creating sources directory with README..."
	@mkdir -p $(PACKAGE_DIR)/sources
	@cp sources/README.md $(PACKAGE_DIR)/sources/

	@echo "Copying root files..."
	@cp SKILL.md CLAUDE.md AGENTS.md README.md ROADMAP.md log.md .gitignore $(PACKAGE_DIR)/

	@echo "Creating wiki/index.md..."
	@echo "# Wiki Index" > $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "> Knowledge base entry point. Start here to explore or add new content." >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "## Recent Activity" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "See [log.md](../log.md) for full history." >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "## Quick Start" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "1. Add source materials to \`sources/\`" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "2. Ask your agent: \"请摄入 sources/[filename] 到 wiki\"" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "3. Explore and query the generated knowledge" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "## Status" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "- 🟡 Empty — waiting for first ingest" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "---" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "" >> $(PACKAGE_DIR)/wiki/index.md
	@echo "*Last updated: $(shell date +%Y-%m-%d)*" >> $(PACKAGE_DIR)/wiki/index.md

	@echo "Creating wiki directory..."
	@mkdir -p $(PACKAGE_DIR)/wiki
	@echo "Note: sources/ directory will be created by user"

	@echo "Cleaning Python cache files..."
	@find $(PACKAGE_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(PACKAGE_DIR) -name "*.pyc" -delete 2>/dev/null || true

	@echo "Creating archive..."
	@cd $(RELEASE_DIR) && ( \
		if command -v zip >/dev/null 2>&1; then \
			zip -rq $(PACKAGE_NAME).zip $(PACKAGE_NAME)/; \
			echo "Created: $(PACKAGE_NAME).zip"; \
		elif command -v tar >/dev/null 2>&1; then \
			tar -czf $(PACKAGE_NAME).tar.gz $(PACKAGE_NAME)/; \
			echo "Created: $(PACKAGE_NAME).tar.gz"; \
		else \
			echo "Warning: No archive tool found (install zip or tar)"; \
		fi \
	)

	@echo ""
	@echo "Release $(VERSION) created successfully!"
	@echo "Location: $(PACKAGE_DIR)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Archive: $(PACKAGE_NAME).zip (or .tar.gz)"
	@echo "  2. Upload to Clawhub"
	@echo "  3. git tag v$(VERSION) && git push origin v$(VERSION)"

# Clean all releases
clean:
	@rm -rf $(RELEASE_DIR)
	@echo "All releases cleaned"
