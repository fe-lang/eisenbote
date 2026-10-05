# crier

A replacement for [towncrier](https://towncrier.readthedocs.io/) written in
[Fe](https://github.com/argotorg/fe) and compiled with Fe's experimental native
backend. It covers the release notes process of the Fe repository: news
fragments in `newsfragments/` are assembled into `CHANGELOG.md` at release
time.

For the Fe configuration crier produces the same bytes as towncrier 25.8. The
test suite checks this on a range of edge cases and by replaying all 38 Fe
releases since 2021.

## Usage

| Fe release step | with towncrier | with crier |
| --- | --- | --- |
| preview the notes | `towncrier build --draft --version X` | `crier draft --version X` |
| compile the notes (`make notes`) | `towncrier build --yes --version X` | `crier build --yes --version X` |
| CI: reject misnamed fragments | `newsfragments/validate_files.py` | `crier check` |
| before tagging: no fragments left | `validate_files.py is-empty` | `crier check --empty` |

`build` inserts the notes behind the `[//]: # (towncrier release notes start)`
marker, stages `CHANGELOG.md` and removes the consumed fragments with
`git rm` (or asks first without `--yes`; `--keep` keeps them). `--date`
overrides today's date, `--dir` and `--file` the fragment directory and the
changelog.

Fragments are named `<issue>.<type>[.<counter>].md` with the types
`feature`, `bugfix`, `performance`, `doc`, `removal`, `internal` and `misc`.
An issue starting with `+` means there is no issue. See the Fe repository's
`newsfragments/README.md`.

## Building

crier needs a Fe compiler built with the `cranelift` feature, on x86-64
Linux or AArch64 macOS:

```sh
make FE=/path/to/fe          # builds out/crier
make test FE=/path/to/fe     # Fe unit tests and tests/test_crier.py
```

`tests/test_crier.py` compares against towncrier when it is installed, and
replays the Fe history when `FE_REPO` points at a clone of the Fe repository.

## Design

Native Fe programs can currently only use stdin, stdout, process arguments
and heap buffers (`std::native::ByteBuffer`); there is no file system access.
So the work is split:

- `out/crier` (the Fe program in `src/`) does everything: it parses fragment
  names, groups and sorts entries, renders the markdown, inserts it into the
  changelog and validates the fragment directory. It reads the files as a
  stream of records on stdin, each a header line followed by the raw bytes:
  `F <length> <file name>` for a file of the fragment directory and
  `C <length>` for the changelog. It writes its result, or an error message
  with a nonzero exit status, to stdout.
- `bin/crier` (a POSIX shell script) produces that stream, writes the result
  back and runs `git`.

The configuration (types, titles, issue links, marker) lives in
`src/config.fe` and mirrors the `[tool.towncrier]` table in Fe's
`pyproject.toml`.

Differences from towncrier:

- Fragments are read in byte order of their names. towncrier uses the file
  system's directory order, so the order of entries that sort as equal (for
  example several fragments of the same issue) can differ between machines.
  crier's order is deterministic.
- Only what the Fe configuration uses is implemented: markdown output with
  the default template, no sections, no text wrapping, no custom templates,
  no per-release files, no `create` command.
- Whitespace handling uses ASCII whitespace where Python would also strip
  Unicode spaces.

## Fe compiler issues found while writing crier

Writing crier ran into several compiler bugs. Each has a branch with a fix,
tests and a newsfragment in the Fe repository. The workarounds in this
repository can go once those are merged:

- `fix/diagnostics-color-choice`: `--color never` was ignored for diagnostics.
- `fix/runtime-as-bytes`: `AsBytes::as_bytes` failed in codegen for values
  that aren't literals at the call site. crier uses its own `Literal` trait
  over `String::as_bytes` instead.
- `fix/string-literal-const-generic-inference`: a string literal couldn't
  infer `N` of a `String<N>` or `[u8; N]` parameter.
- `fix/loop-fresh-buffer-move-conflict`: false move and borrow conflicts after
  raw byte writes through a `mut` buffer parameter, for example a buffer
  released in a loop. crier moves such loop bodies into helper functions
  and copies the process arguments before borrowing its state mutably.
- A borrow checking performance problem: compiling crier takes minutes.
