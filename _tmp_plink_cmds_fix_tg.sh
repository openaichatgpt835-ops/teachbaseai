docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update portal_users_access set telegram_username='lagutin_adm' where portal_id=14 and user_id='1' and kind='bitrix';"
