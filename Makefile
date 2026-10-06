# Requires a Fe compiler built with the `cranelift` feature (native backend).
FE ?= fe
SOURCES = fe.toml $(wildcard ingots/*/fe.toml ingots/*/src/*.fe)

# The last executable that built and passed the tests with Fe's master branch
# (see .github/workflows/latest-fe.yml).
RELEASE_URL ?= https://github.com/fe-lang/eisenbote/releases/download/last-working
PLATFORM = $(shell uname -m)-$(shell uname -s | tr A-Z a-z)

out/eisenbote: $(SOURCES)
	@echo "Compiling eisenbote. fe prints nothing until it is done, which takes"
	@echo "several minutes. (\`make download\` fetches the last working executable.)"
	$(FE) build --backend native --ingot eisenbote --out-dir out .

# Download the last working executable instead of building one.
.PHONY: download
download:
	mkdir -p out
	curl -fsSL -o out/eisenbote "$(RELEASE_URL)/eisenbote-$(PLATFORM)"
	chmod +x out/eisenbote

.PHONY: test
test: out/eisenbote
	$(FE) test --backend native .
	python3 tests/test_eisenbote.py

.PHONY: clean
clean:
	rm -rf out
