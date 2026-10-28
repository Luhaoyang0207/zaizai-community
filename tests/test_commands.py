from zaizai.commands import LfgDecision, ParsedCommand, decide_lfg, parse_lfg_command
from zaizai.models import Mode

CMDS = {"pw": Mode.RANKED, "pp": Mode.MATCH}


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
    assert parse_lfg_command("  !pp x", CMDS) == ParsedCommand(Mode.MATCH, "x")


def test_multiline_kept():
    assert parse_lfg_command("!pw a\nb", CMDS) == ParsedCommand(Mode.RANKED, "a\nb")


def test_fullwidth_disabled():
    assert parse_lfg_command("！pw x", CMDS, accept_fullwidth=False) is None


def test_empty_commands():
    assert parse_lfg_command("!pw x", {}) is None


def test_decide_none():
    assert decide_lfg(None, Mode.RANKED, Mode.RANKED) is LfgDecision.IGNORE


def test_decide_wrong_channel():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, Mode.MATCH, Mode.RANKED) is LfgDecision.IGNORE
    assert decide_lfg(p, None, Mode.RANKED) is LfgDecision.IGNORE


def test_decide_need_voice():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, Mode.RANKED, None) is LfgDecision.NEED_VOICE
    assert decide_lfg(p, Mode.RANKED, Mode.MATCH) is LfgDecision.NEED_VOICE


def test_decide_ok():
    p = ParsedCommand(Mode.RANKED, "x")
    assert decide_lfg(p, Mode.RANKED, Mode.RANKED) is LfgDecision.OK
