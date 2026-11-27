# nanorc

Syntax highlighting for nano, in the spirit of VS Code's **Dark+** theme, for the files I edit most:

| File | Syntax | Covers |
|---|---|---|
| [powershell.nanorc](usr/local/share/nano/powershell.nanorc) | `powershell` | `.ps1`, `.psm1` scripts and modules |
| | `powershell-data` | `.psd1` module manifests and data files (hashtables of literals, so no command or keyword colors) |
| [yaml.nanorc](usr/local/share/nano/yaml.nanorc) | `yaml` | any `.yml` / `.yaml` |
| | `ansible` | Ansible YAML: playbooks, roles, inventories, vars (see [below](#which-yaml-files-count-as-ansible)) |
| [json.nanorc](usr/local/share/nano/json.nanorc) | `json` | `.json`, `.jsonc`, `.json5`, `.code-workspace`, `tsconfig.json` and similar |

The `yaml` and `json` syntaxes replace the ones bundled with nano. When several syntaxes match a file, nano uses the one defined last, and `~/.nanorc` loads after the system's `/etc/nanorc`.

## Colors

The colors are VS Code Dark+ hues, plus the status colors Ansible uses for its output (the same scheme as my PowerShell `$PSStyle`): **green = true/ok, red = false/error, yellow = warning.**

| Role | Color | PowerShell | YAML / Ansible | JSON |
|---|---|---|---|---|
| comment | italic `#695` green | `# ...`, `<# #>` (help keywords bold) | `# ...`, `{# #}` | `//`, `/* */` |
| declaration | `#59d` blue | `function`, `param`, `begin`, `$null` | keys, `null` | `null` |
| control | `#c8c` purple | `if`, `foreach`, `try`, `return`; `#Requires` (bold) | task keywords (`when`, `loop`, `become`, `notify`...), `{{ }}` `{% %}`, block scalars `\|` `>` | escapes `\n` |
| command | `#dda` yellow | `Get-ChildItem`, `.Trim()`, `[Math]::Round` | modules (`ansible.builtin.copy`, `template`...), Jinja filters | |
| parameter | `#9ab` grey-blue | `-Path` | | |
| variable | `#9df` light blue | `$path`, `$env:HOME`, `@splat`, `.psd1` keys | Jinja expressions | keys |
| automatic | `#4cf` | `$_`, `$PSScriptRoot`, `$args`... | | |
| type | `#4cb` teal | `[string]`, `[Parameter()]` | anchors `&x` `*x`, tags `!!str` | |
| string | `#c97` orange | `'...'` (literal), `"..."` (variables shown inside) | plain and quoted values | strings |
| number | `#bca` light green | `42`, `0x1F`, `10KB` | numbers | numbers |
| ok | green | `$true` | `true`, `yes`, `on` | `true` |
| error | red | `$false` | `false`, `no`, `off` | `false` |
| warning | bold yellow | | `{{var}}` without spaces | |
| invalid | red background | trailing whitespace | trailing whitespace, tab indentation, unclosed `{{` / `{%` | trailing whitespace, `,]` |

Operators (`-eq`, `-and`, `=`) and punctuation stay in the terminal's default color, as they do in VS Code.

### Which YAML files count as Ansible

nano picks a syntax from the file's path only, so a `.yml` file gets the `ansible` syntax when its path looks like Ansible:
- it's under a `tasks/`, `handlers/`, `vars/`, `defaults/`, `meta/`, `group_vars/`, `host_vars/`, `inventory/`, `inventories/`, `playbooks/`, `roles/` or `molecule/` directory,
- or a directory or file name in its path contains `ansible` or `playbook`,
- or it's named `site.yml`, `requirements.yml` or `galaxy.yml`.

Other YAML files (Compose, Kubernetes, CI configs) get plain `yaml` highlighting in the same palette, without module names or task keywords.

Inside an `ansible` file, a variable named like a task keyword (for example `retries:` under `vars:`) is still colored as a keyword. nano can't tell the two apart.

## Requirements

nano **7.0 or later**, and a terminal with 256 colors (`TERM=xterm-256color` or similar). The colors are written as `#rgb`, which nano 7.0 introduced. nano approximates them on 256-color terminals.

| Distribution | nano | Works |
|---|---|---|
| RHEL / Rocky / Alma 10, Fedora | 8.x | yes |
| Ubuntu 24.04, Debian 12 | 7.2 | yes |
| RHEL / Rocky / Alma 9 | 5.6 | no: nano reports "Mistakes in ...nanorc" and skips those colors |

## Install

```bash
cp .nanorc ~/.nanorc
sudo mkdir -p /usr/local/share/nano
sudo cp usr/local/share/nano/*.nanorc /usr/local/share/nano/
```

Only read permission is needed on the `*.nanorc` files.

**Upgrading from an older copy:** you can delete `/usr/local/share/nano/ansible.nanorc`. Its syntax moved into `yaml.nanorc`, which loads after it and replaces it, so a leftover copy is unused but harmless.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests open each file in [tests/samples/](tests/samples/) in a real nano, through a pseudo-terminal, and check the color nano draws for each token. [tests/nano_render.py](tests/nano_render.py) rebuilds the screen from nano's output.

The rc file the tests use loads nano's bundled syntaxes first, the same way `/etc/nanorc` does on a real system, so the tests also confirm these files override the bundled `yaml` and `json` syntaxes.

To see what nano draws for any file:

```bash
python3 tests/nano_render.py <rcfile> <file>
```

CI runs the tests on every pull request.
