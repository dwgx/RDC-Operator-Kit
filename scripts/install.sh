#!/usr/bin/env bash
set -euo pipefail
terminal=false
for arg in "$@"; do
  case "$arg" in
    --with-terminal) terminal=true ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
rdc_source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
rdc_python="${RDC_PYTHON:-python3}"
"$rdc_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'
"$rdc_python" - "$rdc_source_root" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
marker = root / '.rdc-install.json'
venv = root / '.venv'
# A normal venv may link bin/python to the base interpreter. Its containing
# bin directory must still belong to this environment, not redirect elsewhere.
for path in (venv, venv / 'bin', marker, root / 'config.local.json', root / 'tools'):
    if path.is_symlink():
        raise SystemExit('Linked installation path refused: ' + path.name)
if venv.exists() and not marker.exists():
    raise SystemExit('Unowned .venv exists; use a fresh source directory.')
if marker.exists():
    state = json.loads(marker.read_text())
    if state.get('project') != 'rdc-operator-kit' or state.get('install_root') != str(root):
        raise SystemExit('Install ownership mismatch')
else:
    marker.write_text(json.dumps({'project':'rdc-operator-kit','install_root':str(root),'schema_version':1}))
PY
if [ ! -d "$rdc_source_root/.venv" ]; then "$rdc_python" -m venv "$rdc_source_root/.venv"; fi
rdc_python="$rdc_source_root/.venv/bin/python"
"$rdc_python" -m pip install --disable-pip-version-check "$rdc_source_root"
if "$terminal"; then "$rdc_python" -m pip install --disable-pip-version-check 'smartcli-toolkit==0.3.5'; fi
"$rdc_python" - "$rdc_source_root" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
config = root / 'config.local.json'
if not config.exists():
    data = {'schema_version':1,'allowed_roots':[str(root)],'observation_ttl_seconds':120}
    terminal = root / '.venv/bin/smartcli-tui'
    if terminal.is_file(): data['smartcli'] = [str(terminal)]
    config.write_text(json.dumps(data, indent=2), encoding='utf-8')
else:
    print('Existing config.local.json preserved.')
PY
"$rdc_python" -m rdc_operator --config "$rdc_source_root/config.local.json" --state "$rdc_source_root/.rdc-state" doctor
printf '%s\n' 'Installed CLI core. Desktop UIA requires Windows; browser control uses its separate official connector.'
