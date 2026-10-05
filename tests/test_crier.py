#!/usr/bin/env python3
"""Tests for crier.

Most cases compare crier with towncrier (the reference implementation it
replaces) on the same input, byte for byte. crier-bin gets the fragments in
os.listdir order, which is the order towncrier sees; the `crier` script itself
sorts them by name, which only matters for entries that sort as equal.

Environment:
  CRIER_BIN   the native executable (default: out/crier)
  TOWNCRIER   the towncrier executable (default: towncrier on PATH); the
              comparisons are skipped without it
  FE_REPO     a clone of argotorg/fe; enables replaying its past releases
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = os.environ.get("CRIER_BIN", str(ROOT / "out" / "crier"))
SCRIPT = str(ROOT / "bin" / "crier")
TOWNCRIER = os.environ.get("TOWNCRIER") or shutil.which("towncrier")
FE_REPO = os.environ.get("FE_REPO")

# The [tool.towncrier] table of the Fe repository, which crier's config mirrors.
PYPROJECT = """\
[tool.towncrier]
filename = "CHANGELOG.md"
directory = "newsfragments"
underlines = ["", ""]
issue_format = "[#{issue}](https://github.com/argotorg/fe/issues/{issue})"
start_string = "[//]: # (towncrier release notes start)"
title_format = "## {version} ({project_date})"
""" + "".join(
    f'\n[[tool.towncrier.type]]\ndirectory = "{d}"\nname = "{n}"\nshowcontent = {s}\n'
    for d, n, s in [
        ("feature", "Features", "true"),
        ("bugfix", "Bugfixes", "true"),
        ("performance", "Performance improvements", "true"),
        ("doc", "Improved Documentation", "true"),
        ("removal", "Deprecations and Removals", "true"),
        ("internal", "Internal Changes - for Fe Contributors", "true"),
        ("misc", "Miscellaneous changes", "false"),
    ]
)

MARKER = "[//]: # (towncrier release notes start)"


def stream(directory, changelog=None):
    out = bytearray()
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            data = Path(path).read_bytes()
            out += b"F %d %s\n" % (len(data), name.encode())
            out += data
    if changelog is not None and os.path.isfile(changelog):
        data = Path(changelog).read_bytes()
        out += b"C %d\n" % len(data)
        out += data
    return bytes(out)


def crier_bin(*args, input=b""):
    return subprocess.run([BIN, *args], input=input, capture_output=True)


class Project:
    """A temporary project with a fragment directory and a changelog."""

    def __init__(self, fragments, changelog=None):
        self.dir = Path(tempfile.mkdtemp(prefix="crier-test-"))
        (self.dir / "pyproject.toml").write_text(PYPROJECT)
        news = self.dir / "newsfragments"
        news.mkdir()
        for name, content in fragments.items():
            data = content if isinstance(content, bytes) else content.encode()
            (news / name).write_bytes(data)
        if changelog is not None:
            (self.dir / "CHANGELOG.md").write_bytes(changelog.encode())

    @property
    def news(self):
        return self.dir / "newsfragments"

    @property
    def changelog(self):
        return self.dir / "CHANGELOG.md"

    def git_init(self):
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        subprocess.run(git + ["-C", str(self.dir), "add", "-A"], check=True)
        subprocess.run(git + ["-C", str(self.dir), "commit", "-qm", "init"], check=True)

    def towncrier(self, *args):
        return subprocess.run(
            [TOWNCRIER, *args], cwd=self.dir, capture_output=True, input=b""
        )

    def cleanup(self):
        shutil.rmtree(self.dir)


def fragments_case(**kwargs):
    return kwargs


# name -> (fragments, existing changelog or None)
CASES = {
    "empty": ({}, None),
    "tooling only": ({"README.md": "readme\n", "validate_files.py": "print()\n"}, None),
    "one of each type": (
        {
            "1.feature.md": "A feature.\n",
            "2.bugfix.md": "A fix.\n",
            "3.performance.md": "Faster.\n",
            "4.doc.md": "Docs.\n",
            "5.removal.md": "Gone.\n",
            "6.internal.md": "Internal.\n",
            "7.misc.md": "Hidden misc text.\n",
        },
        None,
    ),
    "numeric issue order": (
        {f"{n}.bugfix.md": f"Fix {n}.\n" for n in [10, 2, 1, 100, 33]},
        None,
    ),
    "leading zeros": ({"007.bugfix.md": "Bond.\n", "08.bugfix.md": "Eight.\n"}, None),
    "counters": (
        {
            "5.feature.md": "Base.\n",
            "5.feature.1.md": "First.\n",
            "5.feature.2.md": "Second.\n",
            "4.feature.1.md": "Lower issue.\n",
        },
        None,
    ),
    "merged issues": (
        {
            "3.bugfix.md": "Same text.\n",
            "1.bugfix.md": "Same text.\n",
            "2.bugfix.md": "Other text.\n",
            "2.bugfix.1.md": "Same text.\n",
        },
        None,
    ),
    "same issue twice": ({"9.bugfix.md": "Twice.\n", "9.bugfix.1.md": "Twice.\n"}, None),
    "orphans": (
        {
            "+zeta.feature.md": "Zeta comes last.\n",
            "+alpha.feature.md": "`code` first by backtick.\n",
            "+b.feature.md": "Added lowercase.\n",
            "+c.feature.md": "Added Uppercase.\n",
            "+umlaut.feature.md": "Ändert Ümlaute.\n",
            "12.feature.md": "With an issue.\n",
            "+same.feature.md": "With an issue.\n",
        },
        None,
    ),
    "misc without content": (
        {
            "8.misc.md": "Not shown.\n",
            "3.misc.md": "Not shown either.\n",
            "+orphan.misc.md": "Orphan misc is shown.\n",
        },
        None,
    ),
    "named issues": (
        {
            "omega.bugfix.md": "Omega.\n",
            "alpha.bugfix.md": "Alpha.\n",
            "gh-10.bugfix.md": "Gh ten.\n",
            "gh-4.bugfix.md": "Gh four.\n",
            "#3.bugfix.md": "Hash three.\n",
            "#11.bugfix.md": "Hash eleven.\n",
            "2.bugfix.md": "Two.\n",
            "a1b.bugfix.md": "A1b.\n",
            "a01b.bugfix.md": "A01b.\n",
        },
        None,
    ),
    "odd names": (
        {
            "1.feature": "No extension.\n",
            "2.feature.extra.md": "Extra part.\n",
            "1.2.bugfix.md": "Dotted issue.\n",
            "3.unknown.md": "Unknown type is ignored.\n",
            "notes.txt": "Not a fragment.\n",
            ".gitkeep": "",
            "README.rst": "Ignored.\n",
            "4.feature.bugfix.md": "Last configured type wins.\n",
            ".feature.md": "Empty issue.\n",
        },
        None,
    ),
    "content shapes": (
        {
            "1.feature.md": "\n\n  Leading and trailing whitespace.  \n\n\n",
            "2.feature.md": "First paragraph.\n\nSecond paragraph\nwith a wrapped line.\n",
            "3.feature.md": "Has a list:\n\n- one\n- two\n",
            "4.feature.md": "Has a star list:\n\n* one\n* two\n",
            "5.feature.md": "Blank line with spaces\n   \nkeeps it blank.\n",
            "6.feature.md": b"Windows\r\nline endings.\r\n",
            "7.feature.md": b"Old Mac\rline endings.\r",
            "8.feature.md": "No trailing newline",
            "9.feature.md": "Tabs\tinside\tand\n\tindented.\n",
            "10.feature.md": "Unicode: éè \U0001f680 done.\n",
            "+empty.feature.md": "",
            "11.feature.md": "",
        },
        None,
    ),
    "existing changelog": (
        {"1.feature.md": "New.\n"},
        "# Changelog\n\n" + MARKER + "\n## 1.0.0 (2020-01-01)\n\n### Features\n\n- Old.\n",
    ),
    "changelog with spacing around marker": (
        {"1.feature.md": "New.\n"},
        "# Changelog\n\n\n\n" + MARKER + "\n\n\n\n## 1.0.0 (2020-01-01)\n\n- Old.\n",
    ),
    "changelog without marker": ({"1.feature.md": "New.\n"}, "\n\n## Old\n\n- Old.\n"),
    "changelog with only marker": ({"1.feature.md": "New.\n"}, MARKER + "\n"),
    "empty changelog": ({"1.feature.md": "New.\n"}, ""),
    "no changes into changelog": ({}, "# Changelog\n\n" + MARKER + "\n"),
}

VERSION = "2.5.0"
DATE = "2026-10-04"


@unittest.skipUnless(TOWNCRIER, "towncrier is not installed")
class MatchesTowncrier(unittest.TestCase):
    def check_case(self, fragments, changelog):
        project = Project(fragments, changelog)
        try:
            expected = project.towncrier(
                "build", "--draft", "--version", VERSION, "--date", DATE
            )
            actual = crier_bin("draft", VERSION, DATE, input=stream(project.news))
            self.assertEqual(expected.returncode, 0, expected.stderr.decode())
            self.assertEqual(actual.returncode, 0, actual.stdout.decode())
            self.assertEqual(actual.stdout.decode(), expected.stdout.decode())

            built = crier_bin(
                "build", VERSION, DATE, input=stream(project.news, project.changelog)
            )
            consumed = crier_bin("list", input=stream(project.news))
            project.git_init()
            names_before = set(os.listdir(project.news))
            result = project.towncrier(
                "build", "--yes", "--version", VERSION, "--date", DATE
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(built.returncode, 0, built.stdout.decode())
            self.assertEqual(built.stdout.decode(), project.changelog.read_text())
            names_after = set(os.listdir(project.news)) if project.news.exists() else set()
            removed = names_before - names_after
            self.assertEqual(consumed.returncode, 0)
            self.assertEqual(set(consumed.stdout.decode().split("\n")) - {""}, removed)
        finally:
            project.cleanup()

    def test_cases(self):
        for name, (fragments, changelog) in CASES.items():
            with self.subTest(name):
                self.check_case(fragments, changelog)

    def test_duplicate_fragments_are_rejected(self):
        for fragments in [
            {"1.feature.md": "One.\n", "01.feature.md": "Zero one.\n"},
            {".feature.md": "Empty issue.\n", "+orphan.feature.md": "Orphan.\n"},
        ]:
            with self.subTest(sorted(fragments)):
                project = Project(fragments)
                try:
                    expected = project.towncrier(
                        "build", "--draft", "--version", VERSION, "--date", DATE
                    )
                    actual = crier_bin("draft", VERSION, DATE, input=stream(project.news))
                    self.assertNotEqual(expected.returncode, 0)
                    self.assertEqual(actual.returncode, 1)
                    self.assertIn(b"multiple fragments", actual.stdout)
                finally:
                    project.cleanup()

    def test_released_version_is_rejected(self):
        changelog = "# Changelog\n\n" + MARKER + "\n## 2.5.0 (2026-10-04)\n\n- Old.\n"
        project = Project({"1.feature.md": "New.\n"}, changelog)
        try:
            project.git_init()
            expected = project.towncrier(
                "build", "--yes", "--version", VERSION, "--date", DATE
            )
            actual = crier_bin(
                "build", VERSION, DATE, input=stream(project.news, project.changelog)
            )
            self.assertNotEqual(expected.returncode, 0)
            self.assertEqual(actual.returncode, 1)
            self.assertIn(b"already produced", actual.stdout)
        finally:
            project.cleanup()


class Check(unittest.TestCase):
    """`check` replaces newsfragments/validate_files.py."""

    def run_check(self, fragments, *args):
        project = Project(fragments)
        try:
            return crier_bin(*args, input=stream(project.news))
        finally:
            project.cleanup()

    def test_valid(self):
        for fragments in [
            {},
            {"README.md": "x\n", "validate_files.py": "x"},
            {"1.feature.md": "x\n", "+a.bugfix.md": "x\n", "2.bugfix.3.md": "x\n"},
            {"name-with.dots.doc.md": "x\n", "x.misc.md": "\n"},
        ]:
            with self.subTest(sorted(fragments)):
                result = self.run_check(fragments, "check")
                self.assertEqual(result.returncode, 0, result.stdout.decode())

    def test_invalid_names(self):
        for name in [
            "1.feature",
            "1.feature.txt",
            "1.feat.md",
            "1.feature.x.md",
            "feature.md",
            "1.md",
            ".gitkeep",
            "1.feature.md.",
            "notes.txt",
        ]:
            with self.subTest(name):
                result = self.run_check({name: "x\n"}, "check")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout.decode(), f"Unexpected file: {name}\n")

    def test_missing_newline(self):
        for content in ["no newline", ""]:
            with self.subTest(repr(content)):
                result = self.run_check({"1.feature.md": content}, "check")
                self.assertEqual(result.returncode, 1)
                self.assertIn(b"need to end with new line", result.stdout)

    def test_empty(self):
        ok = self.run_check({"README.md": "x\n", "validate_files.py": "x"}, "check-empty")
        self.assertEqual(ok.returncode, 0)
        bad = self.run_check({"1.feature.md": "x\n"}, "check-empty")
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(bad.stdout, b"Unexpected file: 1.feature.md\n")


class Usage(unittest.TestCase):
    def test_bad_arguments(self):
        for args in [[], ["draft"], ["draft", "1.0"], ["list", "x"], ["nope"]]:
            with self.subTest(args):
                result = crier_bin(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"usage", result.stdout)

    def test_malformed_input(self):
        for data in [b"X 1 a\nb", b"F 5 a\nabc", b"F a\n", b"C 1 x\na", b"F 1 a"]:
            with self.subTest(data):
                result = crier_bin("draft", "1", "2", input=data)
                self.assertEqual(result.returncode, 1)
                self.assertIn(b"malformed", result.stdout)


class Script(unittest.TestCase):
    """The bin/crier wrapper, end to end in a git repository."""

    def run_script(self, project, *args):
        env = dict(os.environ, CRIER_BIN=BIN)
        return subprocess.run(
            [SCRIPT, *args], cwd=project.dir, capture_output=True, env=env, input=b""
        )

    def test_build_updates_changelog_and_removes_fragments(self):
        changelog = "# Changelog\n\n" + MARKER + "\n"
        project = Project(
            {"1.feature.md": "Feature.\n", "+x.bugfix.md": "Fix.\n", "README.md": "r\n"},
            changelog,
        )
        try:
            project.git_init()
            (project.news / "2.bugfix.md").write_text("Untracked fix.\n")
            draft = self.run_script(project, "draft", "--version", "1.0", "--date", DATE)
            self.assertEqual(draft.returncode, 0, draft.stderr.decode())
            result = self.run_script(project, "build", "--version", "1.0", "--date", DATE, "--yes")
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(
                project.changelog.read_text(),
                changelog + draft.stdout.decode()[:-1].rstrip() + "\n",
            )
            self.assertEqual(sorted(os.listdir(project.news)), ["README.md"])
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=project.dir, capture_output=True
            ).stdout.decode()
            self.assertIn("M  CHANGELOG.md", status)
            self.assertIn("D  newsfragments/1.feature.md", status)
            check = self.run_script(project, "check", "--empty")
            self.assertEqual(check.returncode, 0, check.stderr.decode())
        finally:
            project.cleanup()

    def test_keep_and_errors(self):
        project = Project({"1.feature.md": "Feature.\n", "bad.txt": "x\n"})
        try:
            project.git_init()
            check = self.run_script(project, "check")
            self.assertEqual(check.returncode, 1)
            self.assertEqual(check.stderr, b"crier: Unexpected file: bad.txt\n")
            result = self.run_script(project, "build", "--version", "1.0", "--keep")
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertIn("1.feature.md", os.listdir(project.news))
            again = self.run_script(project, "build", "--version", "1.0", "--keep")
            self.assertEqual(again.returncode, 1)
            self.assertIn(b"already produced", again.stderr)
        finally:
            project.cleanup()


@unittest.skipUnless(TOWNCRIER and FE_REPO, "needs towncrier and FE_REPO")
class FeHistory(unittest.TestCase):
    """Replay every past Fe release whose notes towncrier compiled."""

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", FE_REPO, *args], capture_output=True, check=True
        ).stdout.decode()

    def test_releases(self):
        commits = self.git(
            "log", "--format=%H", "--grep=^Compile release notes", "--all"
        ).split()
        self.assertTrue(commits)
        compared = 0
        for commit in commits:
            parent = commit + "^"
            tree = self.git("ls-tree", "-r", "--name-only", parent, "--", "newsfragments")
            fragments = {}
            for path in tree.split():
                fragments[path.split("/", 1)[1]] = subprocess.run(
                    ["git", "-C", FE_REPO, "show", f"{parent}:{path}"],
                    capture_output=True,
                    check=True,
                ).stdout
            # The release title that the commit added to the notes.
            header = [
                line[1:] for line in self.git("show", "--format=", commit).split("\n")
                if line.startswith("+## ")
            ][0]
            version, date = header[3:].rstrip(")").rsplit(" (", 1)
            with self.subTest(f"{commit[:9]} {version}"):
                project = Project(fragments)
                try:
                    expected = project.towncrier(
                        "build", "--draft", "--version", version, "--date", date
                    )
                    actual = crier_bin("draft", version, date, input=stream(project.news))
                    self.assertEqual(actual.returncode, 0, actual.stdout.decode())
                    self.assertEqual(actual.stdout.decode(), expected.stdout.decode())
                    compared += 1
                finally:
                    project.cleanup()
        self.assertEqual(compared, len(commits))
        print(f"compared {compared} of {len(commits)} releases", file=sys.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
