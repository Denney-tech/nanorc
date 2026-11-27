#!/usr/bin/env python3
"""Checks what nano actually draws for the sample files in tests/samples/.

    python3 -m unittest discover -s tests

Every sample is opened in a real nano (through a pseudo-terminal, see nano_render.py) with an rc
that loads nano's bundled syntaxes first and this repo's second, as /etc/nanorc + ~/.nanorc do,
so the tests also prove these syntaxes override the bundled yaml/json ones.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import nano_render  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SYNTAX_DIR = os.path.join(REPO, "usr", "local", "share", "nano")
SAMPLES = os.path.join(HERE, "samples")
BUNDLED = "/usr/share/nano"

# The palette (README.md): VS Code Dark+ hues plus Ansible-style status colors.
PALETTE = {
    "comment": "italic,#695",
    "declaration": "#59d",   # function, param, YAML keys, null
    "control": "#c8c",       # if/foreach, Ansible task keywords, Jinja delimiters
    "command": "#dda",       # cmdlets, methods, Ansible modules, Jinja filters
    "parameter": "#9ab",
    "variable": "#9df",      # variables, JSON keys, psd1 keys, Jinja expressions
    "automatic": "#4cf",
    "type": "#4cb",          # [types], YAML anchors and tags
    "string": "#c97",
    "number": "#bca",
    "marker": "#888",        # YAML document markers
    "ok": "green",           # true
    "error": "red",          # false
    "warning": "bold,yellow",  # Jinja spacing
    "directive": "bold,#c8c",  # #Requires
    "help": "bold,italic,#695",  # .SYNOPSIS and other comment-based help keywords
    "invalid": ",red",       # background: trailing whitespace, unclosed Jinja, trailing comma
}


def calibrate(workdir):
    """Style nano draws for each palette entry on this terminal."""
    rc = os.path.join(workdir, "calibrate.rc")
    sample = os.path.join(workdir, "palette.calib")
    with open(rc, "w") as f:
        f.write('syntax calib "\\.calib$"\n')
        for name, spec in PALETTE.items():
            f.write(f'color {spec} "\\<{name}\\>"\n')
    with open(sample, "w") as f:
        f.write("\n".join(PALETTE) + "\n")
    screen = nano_render.render(rc, sample)
    return {name: screen.style_of(name) for name in PALETTE}


class Highlighting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("nano"):
            raise unittest.SkipTest("nano is not installed")
        cls.work = tempfile.mkdtemp(prefix="nanorc-test-")
        cls.styles = calibrate(cls.work)
        cls.rc = os.path.join(cls.work, "system.rc")
        with open(cls.rc, "w") as f:
            if os.path.isdir(BUNDLED):
                f.write(f'include "{BUNDLED}/*.nanorc"\n')
            f.write(f'include "{SYNTAX_DIR}/*.nanorc"\n')
        cls.screens = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def screen(self, sample):
        if sample not in self.screens:
            self.screens[sample] = nano_render.render(self.rc, os.path.join(SAMPLES, sample))
        return self.screens[sample]

    def check(self, sample, expectations):
        screen = self.screen(sample)
        for text, role, *where in expectations:
            occurrence, within = 1, None
            for w in where:
                if isinstance(w, int):
                    occurrence = w
                else:
                    within = w
            with self.subTest(sample=sample, text=text, role=role):
                actual = screen.style_of(text, occurrence, within)
                self.assertEqual(self.styles[role], actual, f"{text!r} should be {role} ({PALETTE[role]})")

    def test_palette_colors_are_distinct(self):
        # Two roles drawn identically would make the checks below meaningless.
        # (directive/help are bold variants of control/comment, invalid is a background.)
        fg_only = {k: v for k, v in self.styles.items() if k not in ("invalid", "directive", "help")}
        self.assertEqual(len(set(fg_only.values())), len(fg_only), self.styles)

    def test_syntax_files_load_without_errors(self):
        for sample in ("sample.ps1", "Sample.psd1", "plain.yml", "roles/demo/tasks/main.yml", "sample.json"):
            with self.subTest(sample=sample):
                status = [line for line in self.screen(sample).text_lines() if "rror" in line or "nknown" in line]
                self.assertEqual([], status)

    def test_powershell(self):
        self.check("sample.ps1", [
            ("#Requires -Version 7.4", "directive"),
            (".SYNOPSIS", "help"),
            ("function", "declaration"),
            ("Get-Thing", "command"),
            ("[CmdletBinding", "type"),
            ("param", "declaration"),
            ("[string]", "type"),
            ("$Path", "variable"),
            ("'x $notvar'", "string"),          # no variables inside single quotes
            ("42", "number"),
            ("if", "control"),
            ("$true", "ok"),
            ("$false", "error"),
            ("Get-ChildItem", "command"),
            ("-Path", "parameter"),
            ("ForEach-Object", "command"),     # not "ForEach" as a keyword
            ("$_", "automatic"),
            (".Trim", "command"),
            ('"Found', "string"),
            ("$Count", "variable", 2),          # inside a double-quoted string
            ("${Path}", "variable"),
            ("[Math]", "type"),
            ("::Round", "command"),
            ("$null", "declaration"),
            ("# trailing comment", "comment"),
        ])
        self.assertEqual("default", self.screen("sample.ps1").style_of("-and").fg)

    def test_powershell_data(self):
        self.check("Sample.psd1", [
            ("# Module manifest", "comment"),
            ("RootModule", "variable"),
            ("'Sample.psm1'", "string"),
            ("7.4", "number"),
            ("'Get-Thing'", "string"),         # a string here, not a command
            ('"Set-Thing"', "string"),
            ("$null", "declaration"),
            ("$false", "error"),
            ("$true", "ok"),
        ])

    def test_plain_yaml(self):
        self.check("plain.yml", [
            ("%YAML 1.2", "marker"),
            ("# compose-style file, not Ansible", "comment"),
            ("services", "declaration"),
            ("nginx:1.27", "string"),
            ("command", "declaration"),        # a plain key here, not an Ansible module
            ("user", "declaration"),
            ("2", "number", "replicas: 2"),
            ("true", "ok"),
            ("off", "error", "debug: off"),
            ("null", "declaration"),
            ("&base", "type"),
            ("*base", "type"),
            ("|", "control"),
            ("!!str", "type"),
        ])

    def test_ansible(self):
        self.check("roles/demo/tasks/main.yml", [
            ("---", "marker"),
            ("Install packages", "string"),
            ("ansible.builtin.dnf", "command"),
            ("{{", "control", 1),
            ("packages", "variable", "{{ packages"),
            ("| default", "command"),
            ("'git'", "string"),
            ("become", "control"),
            ("true", "ok"),
            ("when", "control"),
            ("template", "command"),           # a short module name
            ("'0644'", "string"),
            ("no", "error", "backup: no"),
            ("notify", "control"),
            ("debug", "command"),
            ("{{dnf_result}}", "warning"),
            ("{% if x %}", "control"),
        ])
        unclosed = self.screen("roles/demo/tasks/main.yml").style_of('{{ oops"')
        self.assertEqual(self.styles["invalid"].bg, unclosed.bg)

    def test_json(self):
        self.check("sample.json", [
            ('"name":', "variable"),
            ('"demo"', "string"),
            ("1.5", "number"),
            ("true", "ok"),
            ("false", "error"),
            ("null", "declaration"),
            ('"C:', "string"),                # a ":" inside a string stays string-colored
            ("\\n", "control"),
        ])
        self.assertEqual(self.styles["invalid"].bg, self.screen("sample.json").style_of(",]").bg)


if __name__ == "__main__":
    unittest.main()
