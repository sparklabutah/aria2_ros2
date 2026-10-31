from ament_pep257.main import main
import pytest

MISSING_DOCSTRINGS = ['D100', 'D101', 'D102', 'D103', 'D104', 'D105', 'D106', 'D107']


@pytest.mark.linter
@pytest.mark.pep257
def test_pep257():
    argv = ['.', 'test', '--convention', 'google', '--add-ignore', *MISSING_DOCSTRINGS]
    assert main(argv=argv) == 0, 'Found code style errors / warnings'
