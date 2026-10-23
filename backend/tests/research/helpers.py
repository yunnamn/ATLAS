from sqlalchemy.orm import Session, sessionmaker

from atlas.research.demo import DEMO_OBJECTIVE
from atlas.research.models import ResearchRun
from atlas.research.schemas import RunInput


def make_run(sessions: sessionmaker[Session], **kwargs) -> str:
    data = RunInput(objective=DEMO_OBJECTIVE, **kwargs)
    with sessions() as s:
        run = ResearchRun(
            objective=data.objective, mode=data.mode, request=data.model_dump(mode="json")
        )
        s.add(run)
        s.commit()
        return run.id
