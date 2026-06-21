import os
from pathlib import Path
from cld_providers.antigravity.provider import (
    _dispatch_cwd, _parse_conversation_id, _transcript_path, _extract_model_reply,
)


def test_dispatch_cwd_is_on_system_drive():
    cwd = _dispatch_cwd()
    sysdrive = os.environ.get("SystemDrive", "C:")
    # the dispatch cwd must live on the system drive so agy's POSIX /Users/... path resolves
    assert cwd.upper().startswith(sysdrive.upper())


def test_parse_conversation_id_picks_most_frequent_uuid():
    log = (
        "I0622 server.go:840] Stream goroutine exited for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 conversation_manager.go:601] Stream completed for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 something about aaaaaaaa-1111-2222-3333-444444444444 once\n"
    )
    assert _parse_conversation_id(log) == "4479fde7-507f-4dd9-83c3-f23ce0fe36bd"


def test_parse_conversation_id_none_when_absent():
    assert _parse_conversation_id("no uuids here") is None


def test_transcript_path_layout():
    p = _transcript_path("C:\\Users\\Administrator", "abc")
    assert p.endswith(os.path.join(
        ".gemini", "antigravity-cli", "brain", "abc", ".system_generated", "logs", "transcript.jsonl"))


def test_extract_model_reply_joins_model_steps():
    transcript = (
        '{"step_index":0,"source":"USER_EXPLICIT","content":"hi"}\n'
        '{"step_index":3,"source":"MODEL","type":"PLANNER_RESPONSE","content":"READY"}\n'
        '{"step_index":4,"source":"SYSTEM","content":"ignore me"}\n'
    )
    assert _extract_model_reply(transcript) == "READY"


def test_extract_model_reply_none_when_no_model_step():
    assert _extract_model_reply('{"source":"USER_EXPLICIT","content":"hi"}\n') is None
    assert _extract_model_reply("not json\n\n") is None
