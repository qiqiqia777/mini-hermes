"""The wake-word matcher is a pure function — so it gets deterministic evals.
Whisper mangles phrases in predictable ways; these cases pin the fuzziness."""

import pytest

from minihermes.gateway.voice import matches_wake

SHOULD_WAKE = [
    ("minihermes minihermes", "minihermes minihermes"),
    ("MiniHermes, minihermes!", "minihermes minihermes"),            # punctuation
    ("minihermesminihermes", "minihermes minihermes"),               # whisper drops the space
    ("so anyway minihermes minihermes schedule it", "minihermes minihermes"),  # embedded in speech
    ("minihermez minihermes", "minihermes minihermes"),        # one-letter mangle → fuzzy match
    ("walku waku", "waku waku"),                             # original customizable phrase
    ("Hey MiniHermes", "hey minihermes"),
    ("hey computer, what's up", "hey computer"),
    # regression from the first live session: whisper wrote the wake word in
    # kana — variants after a comma cover other scripts
    ("わくわく", "minihermes minihermes,わくわく"),
    ("わくわくわく", "minihermes minihermes,わくわく"),
    ("小助手你好", "minihermes minihermes,小助手"),
]

SHOULD_NOT_WAKE = [
    ("what a nice day", "minihermes minihermes"),
    ("wake up call at nine", "minihermes minihermes"),
    ("", "minihermes minihermes"),
    ("minihermes minihermes", ""),                        # no wake word configured
    ("walk to work", "minihermes minihermes"),
    ("walku minihermes", "minihermes minihermes"),            # mixed old/new names are not a typo
]


@pytest.mark.parametrize("heard,wake", SHOULD_WAKE, ids=[h for h, _ in SHOULD_WAKE])
def test_wakes(heard, wake):
    assert matches_wake(heard, wake)


@pytest.mark.parametrize("heard,wake", SHOULD_NOT_WAKE, ids=[h or "empty" for h, _ in SHOULD_NOT_WAKE])
def test_stays_asleep(heard, wake):
    assert not matches_wake(heard, wake)
