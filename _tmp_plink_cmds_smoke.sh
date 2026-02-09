set -e
echo SMOKE_1_RAG_QA_START
curl -sS -X POST "http://127.0.0.1:8080/v1/bitrix/portals/2/botflow/client/test" \
  -H "Authorization: Bearer __PORTAL_TOKEN__" \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{
    "text": "Какие есть тарифы?",
    "draft_json": {
      "version": 1,
      "settings": {"mood": "нейтральный", "custom_prompt": "", "use_history": true},
      "nodes": [
        {"id": "start", "type": "start", "title": "Start"},
        {"id": "kb", "type": "kb_answer", "title": "RAG Search"}
      ],
      "edges": [
        {"from": "start", "to": "kb"}
      ]
    },
    "state_json": null
  }'
echo
echo SMOKE_1_RAG_QA_END

echo SMOKE_2_CONSULT_START
curl -sS -X POST "http://127.0.0.1:8080/v1/bitrix/portals/2/botflow/client/test" \
  -H "Authorization: Bearer __PORTAL_TOKEN__" \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{
    "text": "Нужна консультация",
    "draft_json": {
      "version": 1,
      "settings": {"mood": "нейтральный", "custom_prompt": "", "use_history": true},
      "nodes": [
        {"id": "start", "type": "start", "title": "Start"},
        {"id": "ask_need", "type": "ask", "title": "Qualification", "config": {"question": "Что именно вам нужно?", "var": "need"}},
        {"id": "kb", "type": "kb_answer", "title": "RAG Search"},
        {"id": "cta_msg", "type": "message", "title": "CTA", "config": {"text": "Хотите продолжить? Могу показать демо."}},
        {"id": "handoff", "type": "handoff", "title": "CTA / Handoff", "config": {"text": "Передаю менеджеру."}}
      ],
      "edges": [
        {"from": "start", "to": "ask_need"},
        {"from": "ask_need", "to": "kb"},
        {"from": "kb", "to": "cta_msg"},
        {"from": "cta_msg", "to": "handoff"}
      ]
    },
    "state_json": {"vars": {}, "pending": {"var": "need", "next": "kb"}}
  }'
echo
echo SMOKE_2_CONSULT_END

echo SMOKE_3_LEAD_START
curl -sS -X POST "http://127.0.0.1:8080/v1/bitrix/portals/2/botflow/client/test" \
  -H "Authorization: Bearer __PORTAL_TOKEN__" \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{
    "text": "+7 999 111 22 33",
    "draft_json": {
      "version": 1,
      "settings": {"mood": "нейтральный", "custom_prompt": "", "use_history": true},
      "nodes": [
        {"id": "start", "type": "start", "title": "Start"},
        {"id": "ask_phone", "type": "ask", "title": "Qualification", "config": {"question": "Оставьте телефон", "var": "phone"}},
        {"id": "lead", "type": "bitrix_lead", "title": "Action", "config": {"fields": {"TITLE":"Лид с бота","PHONE":[{"VALUE":"{{phone}}","VALUE_TYPE":"WORK"}]}}},
        {"id": "thanks", "type": "message", "title": "Answer Composer", "config": {"text": "Спасибо! Мы свяжемся с вами."}}
      ],
      "edges": [
        {"from": "start", "to": "ask_phone"},
        {"from": "ask_phone", "to": "lead"},
        {"from": "lead", "to": "thanks"}
      ]
    },
    "state_json": {"vars": {}, "pending": {"var": "phone", "next": "lead"}}
  }'
echo
echo SMOKE_3_LEAD_END
