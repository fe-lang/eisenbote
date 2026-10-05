# eisenbote

A replacement for [towncrier](https://towncrier.readthedocs.io/) written in
[Fe](https://github.com/argotorg/fe) and compiled with Fe's experimental native
backend. It covers the release notes process of the Fe repository: news
fragments in `newsfragments/` are assembled into `CHANGELOG.md` at release
time.

For markdown changelogs eisenbote produces the same bytes as towncrier 25.8.
The test suite checks this on a range of edge cases and settings, and by
replaying all 38 Fe releases since 2021.

The repository is a Fe workspace:

- `ingots/eisenbote`: the release notes tool.
- `ingots/toml`: a TOML 1.0 parser, used for the settings. It passes all
  TOML 1.0 cases of the [toml-test](https://github.com/toml-lang/toml-test)
  suite and is meant to become its own library.
- `tools/toml_decoder`: the toml-test decoder for that library.

## Usage

| Fe release step | with towncrier | with eisenbote |
| --- | --- | --- |
| preview the notes | `towncrier build --draft --version X` | `eisenbote draft --version X` |
| compile the notes (`make notes`) | `towncrier build --yes --version X` | `eisenbote build --yes --version X` |
| CI: reject misnamed fragments | `newsfragments/validate_files.py` | `eisenbote check` |
| before tagging: no fragments left | `validate_files.py is-empty` | `eisenbote check --empty` |

`build` inserts the notes behind the start string, stages the changelog and
removes the consumed fragments with `git rm` (or asks first without `--yes`;
`--keep` keeps them). `--date` overrides today's date and `--config` the
settings file.

`check` accepts the files that `build` would consume and towncrier's ignored
names (`README.md` and the like, plus the `ignore` setting), and requires
fragments to end with a new line.

## Settings

eisenbote reads the first of these files in the current directory:

- `eisenbote.toml`, with the settings at the top level,
- `towncrier.toml` or `pyproject.toml`, with the settings in `[tool.towncrier]`.

So a project that uses towncrier works unchanged. The keys and defaults are
towncrier's:

| key | meaning |
| --- | --- |
| `directory` | the fragment directory (required) |
| `filename` | the changelog; must end in `.md` |
| `start_string` | where new releases go (default `<!-- towncrier release notes start -->`) |
| `title_format` | e.g. `"## {version} ({project_date})"`; `false` for none; the number of `#` sets the section level |
| `issue_format` | e.g. `"[#{issue}](https://example.com/{issue})"`; default `#<issue>` for numbers |
| `name`, `version` | for `{name}` in titles; `version` is used without `--version` |
| `orphan_prefix` | fragments without an issue, default `+` |
| `ignore` | file name patterns (`*`, `?`, `[...]`) that are not fragments; setting it makes misnamed files errors |
| `[[type]]` | `directory`, `name`, `showcontent`, in order |
| `[fragment.<directory>]` | `name`, `showcontent`, sorted by directory |

Without types, towncrier's defaults apply (feature, bugfix, doc, removal,
misc). Settings that eisenbote doesn't implement (`template`, `section`,
`package`, `issue_pattern`, `wrap = true`, ...) and unknown keys are errors.

The settings of the Fe repository, as an `eisenbote.toml`:

```toml
directory = "newsfragments"
filename = "CHANGELOG.md"
issue_format = "[#{issue}](https://github.com/argotorg/fe/issues/{issue})"
start_string = "[//]: # (towncrier release notes start)"
title_format = "## {version} ({project_date})"

[[type]]
directory = "feature"
name = "Features"

[[type]]
directory = "bugfix"
name = "Bugfixes"

# ... performance, doc, removal, internal

[[type]]
directory = "misc"
name = "Miscellaneous changes"
showcontent = false
```

## Building

eisenbote needs a Fe compiler built with the `cranelift` feature, on x86-64
Linux or AArch64 macOS:

```sh
make FE=/path/to/fe            # builds out/eisenbote
make test FE=/path/to/fe       # Fe unit tests and tests/test_eisenbote.py
make test FE=... TOML_TEST=/path/to/toml-test   # also the toml-test suite
```

`tests/test_eisenbote.py` compares against towncrier when it is installed,
and replays the Fe history when `FE_REPO` points at a clone of the Fe
repository.

## Design

Native Fe programs can currently only use stdin, stdout, process arguments
and heap buffers (`std::native::ByteBuffer`); there is no file system access.
So the work is split:

- `out/eisenbote` (built from `ingots/eisenbote`) does everything: it parses
  the settings and the fragment names, groups and sorts entries, renders the
  markdown, inserts it into the changelog and validates the fragment
  directory. It reads the files as a stream of records on stdin, each a
  header line followed by the raw bytes: `S <length> <file name>` for the
  settings, `F <length> <file name>` for a file of the fragment directory and
  `C <length>` for the changelog. It writes its result, or an error message
  with a nonzero exit status, to stdout.
- `bin/eisenbote` (a POSIX shell script) finds the settings, produces that
  stream, writes the result back and runs `git`.

Both ingots keep their data in as few heap buffers as possible: borrow
checking time grows quickly with the number of distinct buffers a loop
writes to (see below).

Differences from towncrier:

- Fragments are read in byte order of their names. towncrier uses the file
  system's directory order, so the order of entries that sort as equal (for
  example several fragments of the same issue) can differ between machines.
  eisenbote's order is deterministic.
- Only markdown output with the default template, no sections, no text
  wrapping, no custom templates, no per-release files, no `create` command.
- Whitespace handling uses ASCII whitespace where Python would also strip
  Unicode spaces.

## Fe compiler issues found while writing eisenbote

Each one got a branch with a fix, tests and a newsfragment in the Fe
repository (pushed to `argotorg/fe`). The workarounds in this repository can
go once they are merged:

- `fix/diagnostics-color-choice`: diagnostics ignored `--color never` and
  were colored even when piped.
- `fix/runtime-as-bytes`: `AsBytes::as_bytes` failed in codegen when the value
  wasn't a literal at the call site. Both ingots use a `Key` trait over
  `String::as_bytes` and split long literals instead.
- `fix/string-literal-const-generic-inference`: a string literal couldn't
  infer `N` of a `String<N>` or `[u8; N]` parameter.
- `fix/tuple-assoc-const-array-len`: array lengths given by an associated
  const, such as `const X: [u8; 3] = ("a", "bc").as_bytes()`, were rejected.
- `fix/loop-fresh-buffer-move-conflict`: false move and borrow conflicts after
  raw byte writes through a `mut` buffer parameter. eisenbote moves such loop
  bodies into helper functions and copies the process arguments first.
- `fix/option-copy`: `Option` and `Result` weren't `Copy`, so an `Option`
  field couldn't be read out of `self`.
- `fix/recursive-summary-convergence`: a recursive `mut self` method that
  writes bytes in a loop was rejected. The TOML parser is iterative anyway.
- `fix/continue-in-else-if-chain`: code after an `if`/`else if` chain whose
  last branch returns was compiled as unreachable when an earlier branch
  continued the loop. The UTF-8 check avoids `continue`.
- `fix/assoc-item-trait-scope`: `Self::SIZE` became ambiguous when a trait of
  a dependency, not even imported, had an item of the same name. eisenbote
  reuses the TOML library's `Key` trait.
- `perf/borrowck-reuse-overwrite-replacements` and a branch for the
  exponential cost per written buffer: borrow checking these ingots takes
  minutes.
