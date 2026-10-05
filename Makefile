# Requires a Fe compiler built with the `cranelift` feature (native backend)
# and lutz (the TOML parser) checked out next to this repository.
FE ?= fe
SOURCES = fe.toml $(wildcard ingots/*/fe.toml ingots/*/src/*.fe ../lutz/ingots/lutz/src/*.fe)

out/eisenbote: $(SOURCES)
	$(FE) build --backend native --ingot eisenbote --out-dir out .

.PHONY: test
test: out/eisenbote
	$(FE) test --backend native .
	python3 tests/test_eisenbote.py

.PHONY: clean
clean:
	rm -rf out
