from prefect.utilities.processutils import run_process


async def test_run_process_hides_output(capsys):
    process = await run_process(["echo", "hello world"], stream_output=False)
    assert process.returncode == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


async def test_run_process_captures_stdout(capsys):
    process = await run_process(["echo", "hello world"], stream_output=True)
    assert process.returncode == 0
    out, err = capsys.readouterr()
    assert out == "hello world\n"
    assert err == ""


async def test_run_process_captures_stderr(capsys):
    process = await run_process(
        ["bash", "-c", ">&2 echo hello world"], stream_output=True
    )
    assert process.returncode == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "hello world\n"


async def test_run_process_allows_stdout_fd(tmp_path):
    with open(tmp_path / "output.txt", "wt") as fout:
        process = await run_process(["echo", "hello world"], stream_output=(fout, None))

    assert process.returncode == 0
    assert (tmp_path / "output.txt").read_text() == "hello world\n"


async def test_run_process_allows_stderr_fd(tmp_path):
    with open(tmp_path / "output.txt", "wt") as fout:
        process = await run_process(
            ["bash", "-c", ">&2 echo hello world"], stream_output=(None, fout)
        )
    assert process.returncode == 0
    assert (tmp_path / "output.txt").read_text() == "hello world\n"
