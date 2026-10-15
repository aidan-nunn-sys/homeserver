"""Read and append KEY=value lines in jellyfin/.env."""
from pathlib import Path


def load(path):
    values = {}
    path = Path(path)
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def append(path, values):
    if not values:
        return
    path = Path(path)
    existing = path.read_text() if path.exists() else ''
    with path.open('a') as f:
        if existing and not existing.endswith('\n'):
            f.write('\n')
        for key, value in values.items():
            f.write(f'{key}={value}\n')
