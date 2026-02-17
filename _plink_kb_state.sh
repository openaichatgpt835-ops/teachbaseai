cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -c 'from sqlalchemy import select; from apps.backend.database import get_session_factory; from apps.backend.models.kb import KBJob, KBFile; SessionLocal=get_session_factory(); db=SessionLocal(); jobs=db.execute(select(KBJob).where(KBJob.status.in_(("queued","processing"))).order_by(KBJob.created_at.asc()).limit(30)).scalars().all(); print("ACTIVE_JOBS", len(jobs));
for j in jobs:
 p=j.payload_json or {}; fid=p.get("file_id"); f=db.get(KBFile,int(fid)) if fid else None; print({"job_id":j.id,"portal_id":j.portal_id,"job_type":j.job_type,"job_status":j.status,"file_id":fid,"file_name":(f.filename if f else None),"file_status":(f.status if f else None),"created_at":(j.created_at.isoformat() if j.created_at else None),"updated_at":(j.updated_at.isoformat() if j.updated_at else None),"error":j.error_message});
db.close()'
