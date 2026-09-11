"""Checked collection and per-attempt evidence. No automatic deletion of failures."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
from uuid import uuid4

from cld.candidate import CandidateVerifier, capture_tree, safe_path
from cld.executors._capture import CaptureError, checked


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise OSError(f"Evidence readback mismatch: {path}")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def task_fingerprint(task):
    return hashlib.sha256(json.dumps(asdict(task), sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def slice_directory(repo, sid, run_id=None):
    safe_path(sid)
    if "/" in sid:
        raise CaptureError("Recovery requires a single-component slice ID")
    root = Path(repo).resolve()
    if run_id is not None:
        from cld.build_state import run_directory
        directory = run_directory(repo, run_id) / sid
    else:
        directory = root / ".cld" / sid
    if not directory.resolve().is_relative_to(root):
        raise CaptureError("Recovery directory escapes repository")
    return directory


def recovery_records(repo, sid, run_id=None, include_legacy=False):
    paths = list(slice_directory(repo, sid, run_id).glob("*/outcome.json"))
    if run_id is not None and include_legacy:
        paths.extend(slice_directory(repo, sid).glob("*/outcome.json"))
    return sorted(paths)


@dataclass(frozen=True)
class CollectionResult:
    ok: bool
    commit: str | None = None
    tree: str | None = None
    ref: str | None = None
    error: str | None = None


class RecoverySession:
    def __init__(self, repo, cwd, task, ledger_path, runner, *, session_id=None,
                 base=None, metadata=None):
        self.repo, self.cwd, self.task, self.runner = repo, cwd, task, runner
        self.id = session_id or uuid4().hex
        self.directory = slice_directory(repo, task.id, (metadata or {}).get("run_id")) / self.id
        # Exclusive reservation while the caller holds slice ownership. Never
        # overwrite an existing session, including after a restart.
        self.directory.mkdir(parents=True, exist_ok=False)
        self.base = base or checked(runner, cwd, "rev-parse", "HEAD^{commit}").strip()
        self.attempt = 0
        self.test_run = 0
        self.record = dict(schema_version=1, session_id=self.id, slice_id=task.id,
                           repo=os.path.realpath(repo), ledger=os.path.realpath(ledger_path),
                           task_fingerprint=task_fingerprint(task), base=self.base,
                           worktree=os.path.abspath(cwd), state="reserved" if base else "running",
                           **(metadata or {}))
        self.save()

    def save(self, **values):
        updated = {**self.record, **values}
        atomic_write(self.directory / "outcome.json", json.dumps(updated, indent=2).encode("utf-8"))
        self.record = updated

    def start_attempt(self, attempt):
        self.attempt = attempt
        self.test_run = 0
        self.save(attempts=attempt, retry_policy="prior-candidate-in-place" if attempt > 1 else "fresh-base")

    def write(self, name, text):
        path = self.directory / f"attempt-{self.attempt}" / name
        atomic_write(path, text.encode("utf-8"))
        return path

    def tests(self, output):
        self.test_run += 1
        self.write(f"tests-{self.test_run}.txt", output)

    def dispatch(self, result):
        self.write("dispatch.txt", str(getattr(result, "raw_log", "")))
        self.write("dispatch.json", json.dumps(dict(ok=getattr(result, "ok", None),
                   token_usage=getattr(result, "token_usage", None)), default=repr))
        self.checkpoint("dispatch")

    def verdict(self, result):
        self.write("judge.txt", result.raw_output)
        self.write("judge.json", json.dumps(asdict(result)))
        self.checkpoint("judged")

    def pin_tree(self, tree, name):
        commit = checked(self.runner, self.cwd, "commit-tree", tree, "-p", self.base,
                         "-m", f"cld recovery {self.task.id} {name}").strip()
        ref = f"refs/cld/recovery/{self.id}/{name}"
        checked(self.runner, self.cwd, "update-ref", ref, commit, "0" * len(commit))
        if checked(self.runner, self.cwd, "rev-parse", ref).strip() != commit:
            raise CaptureError("Recovery ref readback mismatch")
        if checked(self.runner, self.cwd, "rev-parse", f"{ref}^{{tree}}").strip() != tree:
            raise CaptureError("Recovery tree readback mismatch")
        return ref

    def checkpoint(self, phase):
        tree = capture_tree(self.runner, self.cwd, self.base)
        name = f"attempt-{self.attempt}-{phase}"
        ref = self.pin_tree(tree, name)
        patch = checked(self.runner, self.cwd, "diff", "--binary", "--full-index",
                        "--no-ext-diff", "--no-textconv", self.base, tree, "--")
        path = self.write(f"{phase}.patch", patch)
        self.validate_patch(path, tree)
        self.save(recovery_ref=ref, recovery_tree=tree, patch=str(path),
                  patch_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def validate_patch(self, path, expected_tree):
        # An isolated index and object directory prove reconstruction without
        # resetting/staging the executor or user checkout, or adding a worktree.
        objects = checked(self.runner, self.cwd, "rev-parse", "--path-format=absolute",
                          "--git-path", "objects").strip()
        with TemporaryDirectory(prefix="cld-patch-check-") as temporary:
            checked(self.runner, temporary, "init", "--bare", "-q",
                    "--object-format=" + ("sha256" if len(self.base) == 64 else "sha1"))
            atomic_write(Path(temporary) / "objects/info/alternates",
                         (Path(objects).as_posix() + "\n").encode("utf-8"))
            checked(self.runner, temporary, "read-tree", self.base)
            if path.stat().st_size:
                checked(self.runner, temporary, "apply", "--cached", "--binary", str(path.resolve()))
            actual = checked(self.runner, temporary, "write-tree").strip()
            if actual != expected_tree:
                raise CaptureError("Recovery patch does not reconstruct the captured tree")

    def failure(self, error):
        # Each operation may itself fail (disk/Git). Caller retains the worktree
        # and includes the failure path in the outcome when evidence is incomplete.
        self.write("error.txt", f"{type(error).__name__}: {error}")
        self.checkpoint("failure")
        self.save(state="failed", error=str(error))

    def collect(self, candidate) -> CollectionResult:
        try:
            verifier = CandidateVerifier(self.runner, self.cwd, self.task, base=candidate.base)
            verifier.prepare_collection(candidate)
            # Anchor the tested tree before user hooks can change either copy.
            self.pin_tree(candidate.tree, "verified")
            self.save(state="verified", candidate=asdict(candidate))
            head = checked(self.runner, self.cwd, "rev-parse", "HEAD^{commit}").strip()
            checked(self.runner, self.cwd, "merge-base", "--is-ancestor", candidate.base, head)
            if checked(self.runner, self.cwd, "rev-parse", f"{head}^{{tree}}").strip() != candidate.tree:
                checked(self.runner, self.cwd, "commit", "-m", f"slice {self.task.id}: accepted by cld")
                head = checked(self.runner, self.cwd, "rev-parse", "HEAD^{commit}").strip()
            if checked(self.runner, self.cwd, "rev-parse", f"{head}^{{tree}}").strip() != candidate.tree:
                raise CaptureError("Collection commit differs from the tested tree")
            verifier.verify_unchanged(candidate)
            ref = f"refs/cld/accepted/{self.id}"
            checked(self.runner, self.cwd, "update-ref", ref, head, "0" * len(head))
            if checked(self.runner, self.cwd, "rev-parse", ref).strip() != head:
                raise CaptureError("Accepted ref readback mismatch")
            outcome = CollectionResult(True, head, candidate.tree, ref)
            self.save(state="collected", collection=asdict(outcome))
            return outcome
        except Exception as exc:
            return CollectionResult(False, error=f"Collection failed: {exc}")


def recover_collected(repo, ledger_path, task, runner, *, run_id=None, include_legacy=False):
    """Reconcile a checked collection whose final ledger write was interrupted.

    Uncollected attempts resume separately. Never infer acceptance from an
    arbitrary branch or an unverified recovery snapshot.
    """
    for path in recovery_records(repo, task.id, run_id, include_legacy):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CaptureError(f"Cannot read recovery record {path}: {exc}") from exc
        if record.get("state") != "collected":
            continue
        if (record.get("repo") != os.path.realpath(repo)
                or record.get("ledger") != os.path.realpath(ledger_path)
                or record.get("task_fingerprint") != task_fingerprint(task)):
            continue
        candidate = record["candidate"]
        collection = record["collection"]
        if (record.get("schema_version") != 1 or collection.get("ok") is not True
                or record["delivery"]["final"]["passed"] is not True):
            raise CaptureError(f"Invalid collected outcome; inspect {path}")
        if checked(runner, repo, "rev-parse", "HEAD^{commit}").strip() != record["base"]:
            raise CaptureError(f"Collected recovery base changed; inspect {path}")
        commit, tree, ref = collection["commit"], collection["tree"], collection["ref"]
        if ref != f'refs/cld/accepted/{record["session_id"]}':
            raise CaptureError(f"Invalid accepted ref; inspect {path}")
        if (checked(runner, repo, "rev-parse", ref).strip() != commit
                or checked(runner, repo, "rev-parse", f"{commit}^{{tree}}").strip() != tree
                or candidate["tree"] != tree or candidate["base"] != record["base"]):
            raise CaptureError(f"Collected recovery no longer verifies: {path}")
        verifier = CandidateVerifier(runner, repo, task, base=record["base"])
        checked(runner, repo, "merge-base", "--is-ancestor", record["base"], commit)
        if verifier.tests_fingerprint != candidate["tests_fingerprint"]:
            raise CaptureError(f"Collected acceptance fingerprint changed: {path}")
        return record, str(path.parent)
    return None
