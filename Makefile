# Requires a Fe compiler built with the `cranelift` feature (native backend).
FE ?= fe
SOURCES = fe.toml $(wildcard ingots/*/fe.toml ingots/*/src/*.fe tools/*/fe.toml tools/*/src/*.fe)

out/eisenbote: $(SOURCES)
	$(FE) build --backend native --ingot eisenbote --out-dir out .

out/toml_decoder: $(SOURCES)
	$(FE) build --backend native --ingot toml_decoder --out-dir out .

.PHONY: test
test: out/eisenbote out/toml_decoder
	$(FE) test --backend native .
	python3 tests/test_eisenbote.py
	# Needs a checkout of https://github.com/toml-lang/toml-test in TOML_TEST.
	if [ -n "$(TOML_TEST)" ]; then python3 tests/toml_test.py $(TOML_TEST); fi

.PHONY: clean
clean:
	rm -rf out
