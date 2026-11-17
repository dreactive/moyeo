import pytest


@pytest.fixture
def room():
    import json
    from pathlib import Path
    return json.loads(Path('docs/contracts/examples/room-snapshot.example.json').read_text(encoding='utf-8'))
