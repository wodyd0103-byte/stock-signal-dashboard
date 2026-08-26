"""digest 실행 시 회고 채점.

`evaluate_due()`가 도는 곳은 원래 두 군데뿐이었다 — APScheduler(스케줄러를 켜야 돈다)와
`/retrospective/evaluate`(앱을 띄우고 버튼을 눌러야 돈다). 둘 다 안 하면 추천은 `open`으로
남아 영영 채점되지 않는다. 실제로 horizon 5일짜리 추천이 71일째 대기 중이었다.

digest는 어차피 매일 도니까 여기서 같이 채점한다.

T04에서 "digest는 DB를 읽기만 한다"고 정했다. 그 규칙의 목적은 **추천 이력을 오염시키지
않는 것**이었고 그건 지킨다 — 여기서 새 추천을 만들지 않는다. 이미 있는 기록에 결과를
채워 넣을 뿐이다. 그래도 쓰기는 쓰기라서 `--no-evaluate`로 끌 수 있게 뒀다.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.analysis_service import close_on
from app.services.retrospective_service import RetrospectiveService

_service = RetrospectiveService()


def evaluate(db: Session) -> tuple[int, str | None]:
    """채점하고 (건수, 오류메시지)를 돌려준다.

    채점은 가격 조회를 타므로 실패할 수 있다. 실패해도 리포트는 나가야 하니
    예외를 올리지 않고 메시지로 돌려준다.
    """
    try:
        return _service.evaluate_due(db, close_on), None
    except Exception as exc:
        return 0, f"회고 채점 실패: {exc}"
