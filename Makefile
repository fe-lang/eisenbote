# Requires a Fe compiler built with the `cranelift` feature (native backend).
FE ?= fe

out/crier: fe.toml $(wildcard src/*.fe)
	$(FE) build --backend native --out-dir out .

.PHONY: test
test: out/crier
	$(FE) test --backend native .
	python3 tests/test_crier.py

.PHONY: clean
clean:
	rm -rf out
