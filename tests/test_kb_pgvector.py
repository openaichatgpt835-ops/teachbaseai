"""pgvector helper safety tests (non-postgres runtime)."""

from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.services.kb_pgvector import vector_to_literal, query_top_chunks_by_pgvector


def test_vector_literal_format():
    lit = vector_to_literal([1, 2.5, 3])
    assert lit == "[1.0,2.5,3.0]"


def test_pgvector_query_returns_empty_on_sqlite():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        rows = query_top_chunks_by_pgvector(
            db,
            portal_id=1,
            audience="staff",
            model="m",
            query_vec=[0.1, 0.2],
            limit=10,
        )
        assert rows == []
    finally:
        db.close()
