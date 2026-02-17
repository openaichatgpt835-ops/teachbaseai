cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -c 'from apps.backend.database import get_session_factory; from apps.backend.models.kb import KBJob,KBFile; Session=get_session_factory(); db=Session();
for jid in (114,115):
 j=db.get(KBJob,jid);
 if not j:
  print("job",jid,"not_found");
  continue
 p=j.payload_json or {}; fid=p.get("file_id"); f=db.get(KBFile,int(fid)) if fid else None;
 print({"job_id":j.id,"status":j.status,"updated_at":(j.updated_at.isoformat() if j.updated_at else None),"error":j.error_message,"file_id":fid,"file":(f.filename if f else None),"file_status":(f.status if f else None),"file_updated":(f.updated_at.isoformat() if (f and f.updated_at) else None),"file_error":(f.error_message if f else None)});
db.close()'
