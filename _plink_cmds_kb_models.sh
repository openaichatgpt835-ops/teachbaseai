docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.services.kb_settings import get_gigachat_settings, get_valid_gigachat_access_token, set_gigachat_settings
from apps.backend.services.gigachat_client import list_models, DEFAULT_API_BASE

factory = get_session_factory()
with factory() as db:
    settings = get_gigachat_settings(db)
    api_base = (settings.get("api_base") or DEFAULT_API_BASE).strip()
    token, err = get_valid_gigachat_access_token(db, force_refresh=True)
    if err or not token:
        print("TOKEN_ERROR", err)
    else:
        items, err2 = list_models(api_base, token)
        if err2:
            print("LIST_ERROR", err2)
        else:
            names = []
            for it in items:
                name = it.get("id") or it.get("name") or it.get("model")
                if name:
                    names.append(str(name))
            print("MODELS", names)
            # pick embedding-like model
            pick = None
            for n in names:
                if "emb" in n.lower():
                    pick = n
                    break
            if not pick and names:
                pick = names[0]
            if pick:
                set_gigachat_settings(db, api_base=None, model=pick, client_id=None, auth_key=None, scope=None, client_secret=None, access_token=None)
                print("MODEL_SET", pick)
PY
