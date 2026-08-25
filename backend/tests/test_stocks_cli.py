"""종목 등록 CLI 테스트 — 임시 DB, 네트워크 없음."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from tools.stocks import __main__ as cli
from tools.stocks import registry


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'stocks.db'}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(cli, "SessionLocal", TestSession)
    return TestSession


# --- resolve -------------------------------------------------------------


def test_resolve_accepts_a_korean_name():
    resolved = registry.resolve("삼성전자")
    assert resolved.ticker == "005930"
    assert resolved.name == "삼성전자"


def test_resolve_fills_the_name_in_from_a_ticker():
    assert registry.resolve("000660").name == "SK하이닉스"


def test_resolve_passes_through_a_ticker_outside_the_list():
    # 대표 목록은 편의용이지 허용 목록이 아니다.
    resolved = registry.resolve("123450")
    assert resolved.ticker == "123450"
    assert resolved.name is None


def test_resolve_rejects_a_ticker_with_path_characters():
    from app.services.data_provider import DataProviderError

    with pytest.raises(DataProviderError):
        registry.resolve("005930/../etc")


# --- watch ---------------------------------------------------------------


def test_watch_add_is_idempotent(db, capsys):
    assert cli.main(["watch", "add", "삼성전자"]) == 0
    assert "추가" in capsys.readouterr().out

    assert cli.main(["watch", "add", "005930"]) == 0
    assert "이미 등록됨" in capsys.readouterr().out

    session = db()
    assert len(registry.list_watch(session)) == 1
    session.close()


def test_watch_rm_reports_a_missing_ticker(db, capsys):
    assert cli.main(["watch", "rm", "005930"]) == 1
    assert "관심종목에 없습니다" in capsys.readouterr().err


def test_watch_rm_deletes(db, capsys):
    cli.main(["watch", "add", "005930"])
    capsys.readouterr()

    assert cli.main(["watch", "rm", "005930"]) == 0

    session = db()
    assert registry.list_watch(session) == []
    session.close()


# --- hold ----------------------------------------------------------------


def test_hold_add_averages_a_second_buy(db, capsys):
    cli.main(["hold", "add", "000660", "--qty", "10", "--avg", "100000"])
    cli.main(["hold", "add", "000660", "--qty", "10", "--avg", "200000"])
    capsys.readouterr()

    session = db()
    holding = registry.list_hold(session)[0]
    assert holding.quantity == 20
    assert holding.avg_price == 150_000  # 재매수 평균
    session.close()


def test_hold_add_replace_overwrites(db, capsys):
    cli.main(["hold", "add", "000660", "--qty", "10", "--avg", "100000"])
    cli.main(["hold", "add", "000660", "--qty", "3", "--avg", "150000", "--replace"])
    out = capsys.readouterr().out

    assert "덮어씀" in out
    session = db()
    holding = registry.list_hold(session)[0]
    assert (holding.quantity, holding.avg_price) == (3, 150_000)
    session.close()


def test_hold_add_rejects_a_non_positive_quantity(db, capsys):
    assert cli.main(["hold", "add", "000660", "--qty", "0", "--avg", "100"]) == 2
    assert "0보다 커야" in capsys.readouterr().err


def test_hold_rm_reports_a_missing_ticker(db, capsys):
    assert cli.main(["hold", "rm", "000660"]) == 1
    assert "보유 종목에 없습니다" in capsys.readouterr().err


# --- list ----------------------------------------------------------------


def test_list_shows_both_tables(db, capsys):
    cli.main(["watch", "add", "005930"])
    cli.main(["hold", "add", "000660", "--qty", "3", "--avg", "150000"])
    capsys.readouterr()

    assert cli.main(["list"]) == 0

    out = capsys.readouterr().out
    assert "관심종목 1건" in out
    assert "보유 종목 1건" in out
    assert "3주 @ 150,000" in out


def test_invalid_ticker_exits_two(db, capsys):
    assert cli.main(["watch", "add", "005930/../etc"]) == 2
    assert "티커를 해석할 수 없습니다" in capsys.readouterr().err
