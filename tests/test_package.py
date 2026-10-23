import json
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tcl-control"


class PackageTests(unittest.TestCase):
    def test_catalog_matches_manifest(self):
        catalog = tomllib.loads((ROOT / "catalog.toml").read_text())["plugin"][0]
        manifest = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        for key in ("id", "name", "version", "author", "license", "plugin_api"):
            self.assertEqual(catalog[key], manifest[key])
        entries = []
        for kind in ("widget", "shortcut", "panel", "service"):
            for entry in manifest.get(kind, []):
                self.assertTrue((PLUGIN / entry["entry"]).is_file())
                entries.append(entry["id"])
        self.assertEqual(len(entries), len(set(entries)))

    def test_translations_cover_script_keys(self):
        english = json.loads((PLUGIN / "translations/en.json").read_text())
        portuguese = json.loads((PLUGIN / "translations/pt.json").read_text())
        self.assertEqual(english.keys(), portuguese.keys())
        for script in PLUGIN.glob("*.luau"):
            for key in re.findall(r'noctalia\.tr\("([^"]+)"\)', script.read_text()):
                self.assertIn(key, english)

    def test_scripts_have_no_development_home_paths(self):
        for path in [*PLUGIN.glob("*.luau"), *PLUGIN.glob("backend/*.py"), PLUGIN / "setup.sh"]:
            text = path.read_text()
            self.assertNotRegex(text, r"/home/[^/]+/")


if __name__ == "__main__":
    unittest.main()
