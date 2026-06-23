import os
import tempfile

from typer.testing import CliRunner

from activityfinder.cli import main


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_add_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orig = os.getcwd()
            os.chdir(tmp)
            try:
                result = self.runner.invoke(
                    main,
                    [
                        "--db", "test.db",
                        "add",
                        "--title",
                        "Test Activity",
                        "--description",
                        "A test",
                        "--category",
                        "other",
                        "--location",
                        "Testville",
                    ],
                )
                assert result.exit_code == 0
                assert "Indexed" in result.output

                result = self.runner.invoke(main, ["--db", "test.db", "list"])
                assert result.exit_code == 0
                assert "Test Activity" in result.output
            finally:
                os.chdir(orig)

    def test_search_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orig = os.getcwd()
            os.chdir(tmp)
            try:
                result = self.runner.invoke(main, ["--db", "test.db", "search", "--query", "nonexistent"])
                assert result.exit_code == 0
                assert "No activities found" in result.output
            finally:
                os.chdir(orig)
