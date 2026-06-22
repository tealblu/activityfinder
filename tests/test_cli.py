from click.testing import CliRunner

from activityfinder.cli import main


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_add_and_list(self) -> None:
        result = self.runner.invoke(
            main,
            [
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

        result = self.runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "Test Activity" in result.output

    def test_search_empty(self) -> None:
        result = self.runner.invoke(main, ["search", "--query", "nonexistent"])
        assert result.exit_code == 0
        assert "No activities found" in result.output
