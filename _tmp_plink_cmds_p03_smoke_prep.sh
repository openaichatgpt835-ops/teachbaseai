# 1) Show current processing statuses

docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, updated_at from kb_files where status='processing' order by updated_at asc limit 10;"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, job_type, status, payload_json, error_message, updated_at from kb_jobs where status='processing' order by updated_at asc limit 10;"

# 2) Pick one ready media file and create processing ingest job + mark file processing and stale

docker exec -i teachbaseai-backend-1 python - <<'PY'
from datetime import datetime, timedelta
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBJob

factory = get_session_factory()
with factory() as db:
    f = db.execute(
        select(KBFile)
        .where(KBFile.status=='ready')
        .where(KBFile.filename.ilike('%.mp3') | KBFile.filename.ilike('%.ogg') | KBFile.filename.ilike('%.mp4'))
        .order_by(KBFile.id.desc())
    ).scalar_one_or_none()
    if not f:
        print('NO_MEDIA_FILE')
    else:
        old = datetime.utcnow() - timedelta(minutes=20)
        f.status = 'processing'
        f.error_message = None
        f.updated_at = old
        db.add(f)
        j = KBJob(portal_id=f.portal_id, job_type='ingest', status='processing', payload_json={'file_id': f.id}, updated_at=old, created_at=old)
        db.add(j)
        db.commit()
        print('SMOKE_FILE_ID', f.id)
        print('SMOKE_JOB_ID', j.id)
PY
