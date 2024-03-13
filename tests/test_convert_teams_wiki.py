from pathlib import Path
import sys
import convert_teams_wiki


def test_empty_page(tmp_path: Path):
    path = tmp_path / "dummy.mht"
    path.write_text(
        '<html data-page="page" data-canvas="canvas" data-site="site" data-list="list"'
        ' data-tabid="tabid" data-slug="slug" data-threadid="threadid"></html>'
    )
    sys.argv = [sys.executable, str(path)]
    convert_teams_wiki.cli_main()
