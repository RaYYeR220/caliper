"""Reading `.env`.

The rule worth testing is the precedence one: a value already in the environment wins. Someone who
exported a key for one command meant it for that command.
"""

from caliper.config import load_env, parse_env


class TestParsing:
    def test_it_reads_key_and_value(self):
        assert parse_env("A=1\nB=2\n") == {"A": "1", "B": "2"}

    def test_comments_and_blank_lines_are_ignored(self):
        assert parse_env("# a note\n\nA=1\n") == {"A": "1"}

    def test_surrounding_quotes_are_stripped(self):
        assert parse_env('A="1"\nB=\'2\'\n') == {"A": "1", "B": "2"}

    def test_a_value_containing_an_equals_sign_survives(self):
        assert parse_env("A=a=b=c\n") == {"A": "a=b=c"}

    def test_whitespace_around_the_assignment_is_trimmed(self):
        assert parse_env("  A = 1  \n") == {"A": "1"}

    def test_a_line_with_no_assignment_is_skipped(self):
        assert parse_env("nonsense\nA=1\n") == {"A": "1"}


class TestLoading:
    def test_it_sets_what_is_missing(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\n", encoding="utf-8")
        env: dict[str, str] = {}
        assert load_env(path, env) == ["A"]
        assert env["A"] == "1"

    def test_it_leaves_an_existing_variable_alone(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=from-file\n", encoding="utf-8")
        env = {"A": "from-the-shell"}
        assert load_env(path, env) == []
        assert env["A"] == "from-the-shell"

    def test_an_empty_value_is_not_set(self, tmp_path):
        """A blank key in the template must not shadow a real one from the environment."""
        path = tmp_path / ".env"
        path.write_text("A=\n", encoding="utf-8")
        env: dict[str, str] = {}
        load_env(path, env)
        assert "A" not in env

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_env(tmp_path / "absent", {}) == []
