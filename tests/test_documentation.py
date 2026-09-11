#!/usr/bin/env python3
"""No-hardware checks for maintained Markdown links and PM-map summaries."""

from collections import Counter, defaultdict
from pathlib import Path
import re
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
MAP = (ROOT / "docs" / "architectures" / "granite_ridge" /
       "9800X3D_PM_TABLE_0x620105.md")
MARKDOWN = tuple(
    path for path in ROOT.rglob("*.md")
    if ".git" not in path.parts
)
MAP_ROW = re.compile(
    r"^\|\s*(0x[0-9A-Fa-f]+(?:-0x[0-9A-Fa-f]+)?)\s*\|"
    r"\s*([0-9]+(?:-[0-9]+)?)\s*\|([^|]*)\|\s*([YN])\s*\|"
    r"([^|]*)\|\s*([^|]*)\|"
)


def github_slug(text):
    """Approximate GitHub's heading slug for the ASCII anchors used here."""
    text = re.sub(r"<[^>]+>", "", text.lower())
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return re.sub(r" +", "-", text.strip())


def heading_anchors(path):
    anchors = set()
    duplicates = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        base = github_slug(match.group(1))
        number = duplicates[base]
        duplicates[base] += 1
        anchors.add(base if number == 0 else f"{base}-{number}")
    return anchors


class TestMarkdownLinks(unittest.TestCase):
    def test_all_local_markdown_links_resolve(self):
        link_pattern = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
        checked = 0
        for source in MARKDOWN:
            for target in link_pattern.findall(source.read_text(encoding="utf-8")):
                target = target.strip().split(maxsplit=1)[0].strip("<>")
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                    continue
                path_text, separator, fragment = target.partition("#")
                destination = (source.parent / unquote(path_text)).resolve() \
                    if path_text else source.resolve()
                checked += 1
                self.assertTrue(
                    destination.exists(),
                    f"{source.relative_to(ROOT)} -> {target}: missing target",
                )
                if separator and destination.suffix.lower() == ".md":
                    self.assertIn(
                        unquote(fragment).lower(), heading_anchors(destination),
                        f"{source.relative_to(ROOT)} -> {target}: missing anchor",
                    )
        self.assertGreater(checked, 0)


class TestPmMapDocumentation(unittest.TestCase):
    def test_9800_map_coverage_and_confidence_summary(self):
        covered = defaultdict(list)
        counts = Counter()
        labels = {}
        text = MAP.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            match = MAP_ROW.match(line.strip())
            if not match:
                continue
            offset_parts = match.group(1).split("-")
            offset_first = int(offset_parts[0], 16)
            offset_final = int(offset_parts[-1], 16)
            first, *last = match.group(2).split("-")
            final = last[0] if last else first
            self.assertEqual(offset_first % 4, 0, f"map line {line_number}")
            self.assertEqual(offset_final % 4, 0, f"map line {line_number}")
            self.assertEqual(offset_first // 4, int(first),
                             f"offset/index start differs on map line {line_number}")
            if len(offset_parts) == 2:
                self.assertEqual(
                    (offset_final - offset_first) // 4 + 1,
                    int(final) - int(first) + 1,
                    f"offset/index range width differs on map line {line_number}",
                )
            confidence = match.group(6).strip().upper()
            current = re.match(r"^(CONFIRMED|HIGH|MED|LOW)\b", confidence)
            category = current.group(1) if current else "UNTAGGED"
            for index in range(int(first), int(final) + 1):
                covered[index].append(line_number)
                labels[index] = category
                counts[category] += 1

        self.assertEqual(set(covered), set(range(457)))
        self.assertEqual(
            {index: lines for index, lines in covered.items() if len(lines) != 1},
            {},
        )
        expected = {
            "CONFIRMED": 86,
            "HIGH": 160,
            "MED": 76,
            "LOW": 66,
            "UNTAGGED": 69,
        }
        self.assertEqual(dict(counts), expected)
        summary_lines = {
            "CONFIRMED": "| CONFIRMED (struct / cross-validated against a system sensor) | 86 |",
            "HIGH": "| HIGH confidence (strong pattern match) | 160 |",
            "MED": "| MED confidence (inferred) | 76 |",
            "LOW": "| LOW confidence (guess) | 66 |",
            "UNTAGGED": "| Untagged / unknown | 69 |",
        }
        for category, summary in summary_lines.items():
            with self.subTest(category=category):
                self.assertIn(summary, text)

        # Current confidence is the leading label in the Confidence column.
        # Historical annotations such as "HIGH (was CONFIRMED)" must not
        # promote a field, and a literal pipe later in an annotation must not
        # make the whole range look untagged.
        for index in range(333, 341):
            self.assertEqual(labels[index], "HIGH")
        for index in range(134, 173):
            self.assertEqual(labels[index], "HIGH")
        self.assertEqual(labels[17], "LOW")
        self.assertEqual(labels[397], "MED")
        self.assertEqual(labels[66], "UNTAGGED")


if __name__ == "__main__":
    unittest.main()
