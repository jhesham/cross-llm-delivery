"""Replay fixtures against one isolated vendored provider, never a real CLI."""
import json
from pathlib import Path
import subprocess
import sys

import cld
from cld.executors import get_executor
from cld.executors.base import SliceTask
from cld.providers_api import load_providers, all_providers


class FakeProcess:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode
        self.error = None if returncode == 0 else "nonzero_exit"

    def metadata(self):
        return {"returncode": self.returncode, "error": self.error}


def main(bundle, provider, repo, fixtures):
    bundle, repo, fixtures = map(Path, (bundle, repo, fixtures))
    assert Path(cld.__file__).resolve().is_relative_to(bundle / "scripts")
    load_providers()
    assert [p.name for p in all_providers()] == [provider]
    cid = "4479fde7-507f-4dd9-83c3-f23ce0fe36bd"
    home = repo.parent / "home"
    transcript = home / ".gemini/antigravity-cli/brain" / cid / ".system_generated/logs/transcript.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_bytes((fixtures / "antigravity/transcript.jsonl").read_bytes())
    calls = []
    mode = "success"

    def runner(argv, cwd, **options):
        if argv[0] == "git":
            result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
            return result.returncode, result.stdout + result.stderr
        calls.append(argv)
        if provider == "codex" and argv == ["codex", "--version"]:
            return FakeProcess("codex-cli fixture\n")
        if provider == "codex" and argv == ["codex", "exec", "--help"]:
            return FakeProcess("--json --ephemeral --sandbox --cd --model --config\n"
                               "If not provided, instructions are read from stdin.\n")
        (repo / "value.py").write_text("VALUE = 42\n", encoding="utf-8")
        rc = 0 if mode == "success" else 1
        if provider == "codex":
            return FakeProcess((fixtures / "codex/success.jsonl").read_text(), rc)
        raw = {
            "antigravity": f"conversation {cid}",
            "opencode": (fixtures / "opencode-run-sample.json").read_text(),
            "cursor": (fixtures / "cursor-run-sample.json").read_text(),
        }[provider]
        return rc, raw

    kwargs = {"runner": runner, "model": "fixture-only", "artifact_dir": repo.parent / "artifacts"}
    if provider == "antigravity":
        kwargs["home"] = str(home)
    executor = get_executor(provider, **kwargs)
    task = SliceTask("A", "Set VALUE to 42", ["value.py"], "test_value.py")
    for mode in ("success", "failed"):
        (repo / "value.py").write_text("VALUE = 0\n")
        result = executor.run(task, repo)
        assert (repo / "value.py").read_text() == "VALUE = 42\n"
        if mode == "success":
            assert result.ok, result.raw_log
            assert result.files_changed == ["value.py"] and "+VALUE = 42" in result.diff
            if provider != "antigravity":
                assert result.token_usage["input"] > 0 and result.token_usage["output"] > 0
            else:
                assert result.token_usage == {}, "missing usage must remain unknown"
        else:
            assert not result.ok and result.diff == "" and result.files_changed == []
    assert calls
    print(json.dumps({"provider": provider, "modes": ["success", "failed"], "offline": True}))


if __name__ == "__main__":
    main(*sys.argv[1:])
