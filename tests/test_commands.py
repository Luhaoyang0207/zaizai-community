from zaizai.commands import (
    LfgDecision,
    ParsedCommand,
    allowed_modes,
    decide_lfg,
    parse_lfg_command,
)
from zaizai.models import Mode

CMDS = {"pw": Mode.RANKED, "pp": Mode.UNRATED}


def test_basic():
    assert parse_lfg_command("!pw 铂钻 3=2", CMDS) == ParsedCommand(Mode.RANKED, "铂钻 3=2")


def test_fullwidth():
    assert parse_lfg_command("！pw 铂钻 3=2", CMDS) == ParsedCommand(Mode.RANKED, "铂钻 3=2")


def test_space_after_bang():
    assert parse_lfg_command("！ pw 铂钻 3=2", CMDS) == ParsedCommand(Mode.RANKED, "铂钻 3=2")
    assert parse_lfg_command("! pw x", CMDS) == ParsedCommand(Mode.RANKED, "x")


def test_case_insensitive():
    assert parse_lfg_command("!PW x", CMDS) == ParsedCommand(Mode.RANKED, "x")


def test_no_text():
    assert parse_lfg_command("!pw", CMDS) == ParsedCommand(Mode.RANKED, "")


def test_prefix_not_matched():
    assert parse_lfg_command("!pwn x", CMDS) is None


def test_not_at_start():
    assert parse_lfg_command("hello !pw x", CMDS) is None


def test_leading_whitespace():
    assert parse_lfg_command("  !pp x", CMDS) == ParsedCommand(Mode.UNRATED, "x")


def test_multiline_kept():
    assert parse_lfg_command("!pw a\nb", CMDS) == ParsedCommand(Mode.RANKED, "a\nb")


def test_fullwidth_disabled():
    assert parse_lfg_command("！pw x", CMDS, accept_fullwidth=False) is None


def test_empty_commands():
    assert parse_lfg_command("!pw x", {}) is None


ALL = {Mode.RANKED, Mode.UNRATED}


def test_decide_none():
    assert decide_lfg(None, ALL, True) is LfgDecision.IGNORE


def test_decide_wrong_command_in_team_channel():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, {Mode.UNRATED}, True) is LfgDecision.IGNORE
    assert decide_lfg(p, set(), True) is LfgDecision.IGNORE


def test_decide_any_command_in_voice_chat():
    for mode in ALL:
        assert decide_lfg(ParsedCommand(mode, "x"), ALL, True) is LfgDecision.OK


def test_decide_need_voice():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, {Mode.RANKED}, False) is LfgDecision.NEED_VOICE
    assert decide_lfg(p, ALL, False) is LfgDecision.NEED_VOICE


def test_decide_ok_in_team_channel():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, {Mode.RANKED}, True) is LfgDecision.OK


TEAM = {500: Mode.RANKED, 501: Mode.UNRATED}


def test_allowed_team_channel_only_its_mode():
    assert allowed_modes(500, False, TEAM, ALL, True) == {Mode.RANKED}
    assert allowed_modes(501, False, TEAM, ALL, True) == {Mode.UNRATED}


def test_allowed_team_channel_mode_without_command():
    assert allowed_modes(501, False, TEAM, {Mode.RANKED}, True) == set()


def test_allowed_voice_chat_all_command_modes():
    assert allowed_modes(900, True, TEAM, ALL, True) == ALL


def test_allowed_voice_chat_disabled():
    assert allowed_modes(900, True, TEAM, ALL, False) == set()


def test_allowed_other_text_channel():
    assert allowed_modes(900, False, TEAM, ALL, True) == set()
