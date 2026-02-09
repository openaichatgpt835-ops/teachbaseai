from apps.backend.services.bot_flow_engine import execute_client_flow_preview


def test_flow_does_not_loop_on_self_edge():
    flow = {
        "version": 1,
        "settings": {"mood": "нейтральный", "custom_prompt": "", "use_history": True},
        "nodes": [
            {"id": "start", "type": "start", "title": "Start"},
            {"id": "msg", "type": "message", "title": "Message", "config": {"text": "Привет"}},
        ],
        "edges": [
            {"from": "start", "to": "msg"},
            {"from": "msg", "to": "msg"},
        ],
    }
    text, _state, trace = execute_client_flow_preview(None, 1, 0, "тест", flow)
    assert text.count("Привет") == 1
    assert any(ev.get("event") == "loop_break" for ev in trace)
