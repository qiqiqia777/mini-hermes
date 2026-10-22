"""DETERMINISTIC EVAL — the cross-model coding runner (minihermes.ops.coding_eval).

We can't call a real model in a hermetic test, so we run a no-op Python script
in place of pi and let the seeded files + the real `verify` command decide
the verdict. That exercises everything that isn't the model: file seeding,
provider/key guards, and — the whole point — that the score is the verify exit
code, not pi's prose."""

from __future__ import annotations

import sys

from minihermes.ops import coding_eval as ce

def _verify(code):
    return f'"{sys.executable}" -c "{code}"'


def _stub_pi(monkeypatch, tmp_path):
    """Keep real subprocesses and verification, replacing only the pi command."""
    stub = tmp_path / "pi stub.py"
    stub.write_text("print('stub pi ran')\n", encoding="utf-8")
    original_which = ce.shutil.which
    original_popen = ce.subprocess.Popen

    def launch(command, *args, **kwargs):
        if isinstance(command, list) and command[:2] == [sys.executable, "--provider"]:
            command = [sys.executable, str(stub), *command[1:]]
        return original_popen(command, *args, **kwargs)

    monkeypatch.setattr(
        ce.shutil, "which",
        lambda name: sys.executable if name == "pi" else original_which(name),
    )
    monkeypatch.setattr(ce.subprocess, "Popen", launch)


def test_verify_pass_is_the_verdict(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    case = {"id": "ok", "input": "n/a",
            "files": {"fizzbuzz.py": "def fizzbuzz(n):\n"
                      "    return 'FizzBuzz' if n%15==0 else 'Fizz' if n%3==0 else 'Buzz' if n%5==0 else str(n)\n"},
            "verify": _verify("from fizzbuzz import fizzbuzz; assert fizzbuzz(15)=='FizzBuzz'; print('ok')")}
    passed, why, secs = ce.run_coding_case("anthropic", "claude-opus-4-8", case)
    assert passed and why == "tests pass"


def test_verify_fail_when_code_is_wrong(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    case = {"id": "bad", "input": "n/a",
            "files": {"fizzbuzz.py": "def fizzbuzz(n):\n    return 'wrong'\n"},
            "verify": _verify("from fizzbuzz import fizzbuzz; assert fizzbuzz(3)=='Fizz'")}
    passed, why, _ = ce.run_coding_case("anthropic", "claude-opus-4-8", case)
    assert not passed                       # pi 'ran' but the code fails verify
    assert "AssertionError" in why          # fail on the code, not a missing executable


def test_missing_key_is_reported(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    passed, why, _ = ce.run_coding_case("xai", "grok-4.5", {"id": "x", "input": "n/a"})
    assert not passed and "api key" in why


def test_unmapped_provider_is_reported(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)
    passed, why, _ = ce.run_coding_case("nope", "whatever", {"id": "x", "input": "n/a"})
    assert not passed and "provider mapping" in why


def test_every_pinned_provider_maps_to_a_pi_provider():
    # the arena's pinned providers must all reach pi, or the coding round can't run them
    for prov in ("anthropic", "openai", "gemini", "kimi", "xai", "glm"):
        assert prov in ce.PI_PROVIDER


def test_coding_cases_load_and_have_verify():
    cases = ce.load_coding_cases()
    assert len(cases) >= 2
    for c in cases:
        assert "id" in c and "input" in c and "verify" in c


def test_coding_case_for_message_matches_trimmed():
    cases = [{"id": "fizz", "input": "Create fizzbuzz.py"}]
    assert ce.coding_case_for_message("  Create fizzbuzz.py ", cases)["id"] == "fizz"
    assert ce.coding_case_for_message("build a website", cases) is None


def test_stream_runner_scores_by_verify_and_emits_lines(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)             # pi = no-op; seeded file provides the code
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    lines = []
    passed, why, secs = ce.run_coding_stream(
        "anthropic", "claude-opus-4-8",
        task="n/a",
        files={"fizzbuzz.py": "def fizzbuzz(n):\n    return 'FizzBuzz' if n%15==0 else str(n)\n"},
        verify=_verify("from fizzbuzz import fizzbuzz; assert fizzbuzz(15)=='FizzBuzz'"),
        on_line=lines.append)
    assert passed is True and why == "tests pass"
    assert any(ln.startswith("$ pi") for ln in lines)   # the launch line streamed
    assert "stub pi ran" in lines                     # the real child process ran


def test_stream_runner_free_form_has_no_verdict(tmp_path, monkeypatch):
    _stub_pi(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    passed, why, _ = ce.run_coding_stream("anthropic", "claude-opus-4-8",
                                          task="build snake", files=None, verify=None,
                                          on_line=lambda _ln: None)
    assert passed is None            # nothing to score -> no pass/fail, it just ran
