from pathlib import Path

from prefect.tasks.files import Move


class TestMove:
    def test_initialization(self):
        m = Move(source_path="source", target_path="target")
        assert m.source_path == "source"
        assert m.target_path == "target"

        m = Move()
        assert m.source_path == ""
        assert m.target_path == ""

    def test_run_move_file_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        m = Move(str(source), str(tmpdir))
        res = m.run()
        exp = tmpdir.join("test")
        assert res == Path(str(exp))
        assert exp.exists()
        assert not source.exists()

    def test_run_move_file_to_file(self, tmpdir):
        source = tmpdir.mkdir("source").join("test")
        source.write_binary(b"test")

        target = tmpdir.join("out")

        m = Move(str(source), str(target))
        res = m.run()
        assert res == Path(str(target))
        assert target.exists()
        assert not source.exists()

    def test_run_move_directory_to_directory(self, tmpdir):
        source = tmpdir.mkdir("source").mkdir("test")

        m = Move(str(source), str(tmpdir))
        res = m.run()
        exp = tmpdir.join("test")
        assert res == Path(str(exp))
        assert exp.exists()
        assert exp.isdir()
        assert not source.exists()
