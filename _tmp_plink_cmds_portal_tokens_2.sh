docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select portal_id, access_token_enc is not null as has_token, expires_at, updated_at from portal_tokens where portal_id=2;"
