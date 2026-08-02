"""백테스트 호가단위/비용 단위 테스트."""
from app.services.backtest_service import round_to_tick, tick_size


def test_tick_size_bands():
    assert tick_size(1500) == 1
    assert tick_size(3000) == 5
    assert tick_size(15000) == 10
    assert tick_size(45000) == 50
    assert tick_size(150000) == 100
    assert tick_size(300000) == 500
    assert tick_size(800000) == 1000


def test_round_to_tick():
    assert round_to_tick(70123) == 70100   # 100원 단위
    assert round_to_tick(3013) == 3015     # 5원 단위
    assert round_to_tick(1850) == 1850     # 1원 단위


def test_backtest_runs_with_costs(enriched_uptrend):
    from app.services.backtest_service import BacktestService
    bt = BacktestService().run("TEST", "1y", enriched_uptrend, 10_000_000, strategy="absolute_score_strategy")
    assert bt.trade_count >= 0
    assert -100 <= bt.total_return <= 100000
    assert "거래세" in bt.note  # 비용 반영 명시
