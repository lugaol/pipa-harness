# pipa_harness installer — thin orchestration over the Python CLI.
#
# Two-layer design: this Makefile only syncs/wires; every component install
# delegates to `bin/pipa install <component>` so logic lives in ONE place.
#
#   make -C install              copy working tree -> ~/.pipa-harness
#   make -C install update       git pull --ff-only (fallback: rsync again)
#   make -C install wire         bin/pipa up --no-apps --no-pull
#   make -C install path         append PATH line to shell rc (idempotent)
#   make -C install uninstall    rm -rf ~/.pipa-harness (CONFIRM=yes required)
#   make -C install ollama       single component: uv ollama litellm graphify dsh opencode apps
#   make -C install comp C=ollama    same thing, parameterized
#
DEST ?= $(HOME)/.pipa-harness
SRC := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
PIPACTL := $(DEST)/bin/pipa

# Runtime junk never synced; .git IS synced so `update` can pull later.
EXCLUDES := node_modules __pycache__ state logs graphify-out .pytest_cache .DS_Store *.log

.DEFAULT_GOAL := install
.PHONY: help install update wire path uninstall comp uv ollama litellm graphify dsh opencode apps

help:
	@echo "pipa_harness installer"
	@echo "  install                 rsync working tree -> $(DEST) (default)"
	@echo "  update                  git -C $(DEST) pull --ff-only, else rsync again"
	@echo "  wire                    cd $(DEST) && bin/pipa up --no-apps --no-pull"
	@echo "  path                    add \$$PATH line to shell rc (idempotent)"
	@echo "  uninstall               remove $(DEST) (requires CONFIRM=yes)"
	@echo "  <component>             install one of: uv ollama litellm graphify dsh opencode apps"
	@echo "  comp C=<component>      same as above, parameterized"

install:
	@command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync not found on PATH"; exit 1; }
	rsync -a --delete $(foreach e,$(EXCLUDES),--exclude '$(e)') "$(SRC)/" "$(DEST)/"
	@echo ""
	@echo "Installed pipa_harness -> $(DEST)"
	@echo "Next:"
	@echo "  make -C install path      # put pipa on \$$PATH"
	@echo "  make -C install wire      # tools + services (no GUI apps, no model pulls)"
	@echo "  pipa status               # health check"

update:
	@if [ ! -d "$(DEST)/.git" ]; then \
		echo "$(DEST) is not a git checkout — rsyncing working tree instead"; \
		$(MAKE) --no-print-directory install; \
	elif git -C "$(DEST)" pull --ff-only; then \
		echo "updated via git -> $(DEST)"; \
	else \
		echo "git pull failed — falling back to rsync of working tree"; \
		$(MAKE) --no-print-directory install; \
	fi

wire:
	@test -x "$(PIPACTL)" || { echo "ERROR: $(PIPACTL) missing — run 'make -C install' first"; exit 1; }
	cd "$(DEST)" && ./bin/pipa up --no-apps --no-pull

# Mirrors services.persist_path() in pipa/services.py — keep in sync.
path:
	@line='export PATH="$(DEST)/bin:$$HOME/.opencode/bin:$$HOME/.local/bin:$$PATH"'; \
	for rc in "$$HOME/.zshrc" "$$HOME/.bashrc"; do \
		case "$$rc" in \
			*.zshrc)  [ -f "$$rc" ] || [ "$${SHELL##*/}" = zsh ] || continue ;; \
			*.bashrc) [ -f "$$rc" ] || [ "$${SHELL##*/}" = bash ] || continue ;; \
		esac; \
		if [ -f "$$rc" ] && grep -qF "$(DEST)/bin" "$$rc" 2>/dev/null; then \
			echo "PATH already in $${rc##*/}"; \
		else \
			printf '\n# pipa_harness (pipa CLI + runtimes + uv tools)\n%s\n' "$$line" >> "$$rc"; \
			echo "PATH added to $${rc##*/} (open a new terminal to pick it up)"; \
		fi; \
	done

uninstall:
	@if [ "$(CONFIRM)" != yes ]; then \
		echo "Refusing to remove $(DEST) without confirmation."; \
		echo "Re-run with: make -C install uninstall CONFIRM=yes"; \
		exit 1; \
	fi
	rm -rf "$(DEST)"
	@echo "Removed $(DEST). Delete the pipa PATH line from your shell rc if you want it gone too."

comp:
	@test -n "$(C)" || { echo "usage: $(MAKE) [-C install] comp C=<uv|ollama|litellm|graphify|dsh|opencode|apps>"; exit 1; }
	$(MAKE) --no-print-directory $(C)

uv ollama litellm graphify dsh opencode apps:
	@test -x "$(PIPACTL)" || { echo "ERROR: $(PIPACTL) missing — run 'make -C install' first"; exit 1; }
	cd "$(DEST)" && ./bin/pipa install $@
