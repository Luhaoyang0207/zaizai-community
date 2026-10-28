from dataclasses import replace
from types import SimpleNamespace

import discord
import pytest

from zaizai.bot import ErrorNotifier, discord_call, enabled_cogs
from zaizai.config import load_config, mode_in_scope
from zaizai.models import Mode


@pytest.fixture
def cfg():
    return load_config("config/settings.toml")


def test_enabled_cogs_respects_config(cfg):
    assert enabled_cogs(cfg) == ["voice_rooms", "lfg", "board", "panel", "admin"]
    only = replace(cfg, modules_enabled=("lfg", "board"))
    assert enabled_cogs(only) == ["lfg", "board"]


def test_unknown_cog_name_raises(cfg):
    bad = replace(cfg, modules_enabled=("lfg", "nope"))
    with pytest.raises(ValueError):
        enabled_cogs(bad)


def test_mode_scope_limits_modes(cfg):
    scoped = replace(cfg, modules_mode_scope=(Mode.MATCH,))
    assert not mode_in_scope(scoped, Mode.RANKED)
    assert mode_in_scope(scoped, Mode.MATCH)


def test_error_notifier_notifies_once_per_key():
    n = ErrorNotifier()
    assert n.should_notify("a") is True
    assert n.should_notify("a") is False
    assert n.should_notify("b") is True


def _exc(cls, status):
    return cls(SimpleNamespace(status=status, reason="x"), "msg")


async def test_discord_call_does_not_retry_forbidden():
    calls = 0

    async def f():
        nonlocal calls
        calls += 1
        raise _exc(discord.Forbidden, 403)

    with pytest.raises(discord.Forbidden):
        await discord_call(f, delay_sec=0)
    assert calls == 1


async def test_discord_call_does_not_retry_not_found():
    calls = 0

    async def f():
        nonlocal calls
        calls += 1
        raise _exc(discord.NotFound, 404)

    with pytest.raises(discord.NotFound):
        await discord_call(f, delay_sec=0)
    assert calls == 1


async def test_discord_call_retries_http_exception_three_times():
    calls = 0

    async def f():
        nonlocal calls
        calls += 1
        raise _exc(discord.HTTPException, 500)

    with pytest.raises(discord.HTTPException):
        await discord_call(f, delay_sec=0)
    assert calls == 3


async def test_discord_call_returns_after_transient_failure():
    calls = 0

    async def f():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise _exc(discord.HTTPException, 500)
        return "ok"

    assert await discord_call(f, delay_sec=0) == "ok"
