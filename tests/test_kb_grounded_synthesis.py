from apps.backend.services.kb_rag import (
    _build_grounded_snippets,
    _grounded_synthesis_answer,
    _enforce_paragraph_evidence,
    _build_line_refs,
    _build_kb_answer_messages,
    _build_entity_list_answer,
    _build_grounded_overview_answer,
    _build_grounded_instruction_answer,
    _build_grounded_windows,
    _evaluate_simple_arithmetic,
    _expand_short_grounded_answer,
    _is_product_settings_query,
    _style_rewrite_topn_answer,
    _rerank_candidates,
    _should_replace_with_claims_answer,
    _should_replace_with_entity_list_answer,
    _should_replace_with_topn_answer,
    _verify_and_ground_answer,
    _ensure_topn_breadth,
    _count_numbered_items,
    _build_topn_answer,
    _strip_topn_caveat_paragraphs,
)


def test_build_grounded_snippets_prefers_relevant_sentences_and_skips_noise():
    chunks = [
        {
            "text": "Anti-trainer benches 180 kg in one rep. Positive music 1, 2, 3.",
            "_score": 0.6,
        },
        {
            "text": "The episode says anti-trainer benches 180 kilograms.",
            "_score": 0.7,
        },
        {
            "text": "Advertisement and promo code in description.",
            "_score": 0.9,
        },
    ]

    out = _build_grounded_snippets("how much does anti trainer bench", chunks, limit=5)

    assert out
    joined = " ".join(out).lower()
    assert "180" in joined
    assert "promo code" not in joined
    assert "positive music" not in joined


def test_keyword_hits_uses_russian_lemma_matching():
    from apps.backend.services.kb_rag import _keyword_hits

    assert _keyword_hits("Тави вместе со спутниками идет через болота.", ["спутник"]) >= 1


def test_evaluate_simple_arithmetic_handles_russian_words():
    assert _evaluate_simple_arithmetic("сколько будет три плюс два") == "Ответ: 5"


def test_numeric_fact_answer_requires_query_keyword_overlap():
    from apps.backend.services.kb_rag import _extract_numeric_fact_answer

    out = _extract_numeric_fact_answer(
        "сколько жмет спартак",
        [{"text": "При заказе до 31 августа вы получите 2 товара по цене 1."}],
    )
    assert out is None


def test_grounded_synthesis_rejects_disclaimer(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return "Как языковая модель, я не могу помочь с этим запросом.", None, {}

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _grounded_synthesis_answer(
        query="who is alexey",
        chunks=[{"text": "Alexey Lagutin is Head of Customer Success.", "_score": 0.4}],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=512,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is None


def test_enforce_paragraph_evidence_drops_weak_paragraphs():
    query = "how much does anti trainer bench"
    chunks = [
        {"text": "Anti-trainer benches 180 kg in one rep.", "_score": 0.7},
    ]
    answer = (
        "Anti-trainer benches 180 kg in one rep.\n\n"
        "This legendary figure changed the whole fitness culture of the world."
    )
    out = _enforce_paragraph_evidence(query, answer, chunks)
    assert "180 kg" in out
    assert "changed the whole fitness culture" not in out


def test_build_line_refs_fallback_for_insufficient_answer():
    answer = "Not enough confirmed data in the knowledge base for this request."
    sources = [
        {"text": "Anti-trainer benches 180 kg.", "filename": "a.mp3", "score": 0.5},
        {"text": "The episode mentions bench press and weight.", "filename": "b.mp3", "score": 0.4},
    ]
    refs = _build_line_refs(answer, sources, query="how much does anti trainer bench")
    assert "0" in refs
    assert len(refs["0"]) >= 1


def test_build_line_refs_caps_refs_per_line_and_keeps_item_cohesion():
    answer = (
        "1. Guard Sign\n"
        "This protective spell blocks the entrance and hides the passage.\n\n"
        "2. Stone Throne\n"
        "A last-resort sign for a critical situation."
    )
    sources = [
        {"text": "Guard Sign blocks the entrance and hides the passage.", "filename": "a.txt", "score": 0.9},
        {"text": "Guard Sign is a protective spell.", "filename": "b.txt", "score": 0.8},
        {"text": "Guard Sign hides the passage from enemies.", "filename": "c.txt", "score": 0.7},
        {"text": "Guard Sign requires a branch and an incantation.", "filename": "d.txt", "score": 0.6},
        {"text": "Stone Throne is used only in a critical situation.", "filename": "e.txt", "score": 0.9},
    ]
    refs = _build_line_refs(answer, sources, query="give top 5 spells")
    assert "0" in refs
    assert len(refs["0"]) <= 3
    assert "1" in refs
    assert len(refs["1"]) <= 3


def test_should_not_replace_good_topn_answer_with_short_claims_answer():
    query = "give top 5 strongest spells and how to cast them"
    current = (
        "1. Guard Sign [1]\n"
        "This spell is created via a guarding incantation.\n\n"
        "2. Curse of Rabbaar Drobdt [2]\n"
        "It requires knowledge of dark magic.\n\n"
        "3. Stone Throne [3]\n"
        "It is used in critical situations."
    )
    claims = (
        "1. Stone Throne is a rare and dangerous spell.\n"
        "2. Giant Weapon is a symbol of strength and power."
    )
    assert _should_replace_with_claims_answer(query, current, claims, [{"text": "x"}]) is False


def test_should_replace_low_quality_answer_with_claims_answer():
    query = "give top 5 strongest spells and how to cast them"
    current = "Как языковая модель, я не могу помочь с этим запросом."
    claims = (
        "1. Stone Throne is a rare and dangerous spell.\n"
        "2. Giant Weapon is a symbol of strength and power."
    )
    assert _should_replace_with_claims_answer(query, current, claims, [{"text": "x"}]) is True


def test_verify_and_ground_preserves_supported_numbered_blocks():
    query = "give top 5 spells"
    chunks = [
        {
            "text": (
                "Guard Sign is easy to create by using a branch and a guarding incantation. "
                "Stone Throne is used only in a critical situation and only once."
            ),
            "_score": 0.8,
        }
    ]
    answer = (
        "1. Guard Sign\n"
        "It is simple and effective to create.\n\n"
        "2. Chain of Wards\n"
        "It reflects attacks from enemies.\n\n"
        "3. Stone Throne\n"
        "It is used only in a critical situation."
    )
    out = _verify_and_ground_answer(query, answer, chunks)
    assert "1. Guard Sign" in out
    assert "3. Stone Throne" in out
    assert "2. Chain of Wards" not in out


def test_enforce_paragraph_evidence_preserves_numbered_blocks():
    query = "give top 5 spells"
    chunks = [
        {
            "text": (
                "Guard Sign is easy to create by using a branch and a guarding incantation. "
                "Stone Throne is used only in a critical situation and only once."
            ),
            "_score": 0.8,
        }
    ]
    answer = (
        "1. Guard Sign\n"
        "It is simple and effective to create.\n\n"
        "2. Chain of Wards\n"
        "It reflects attacks from enemies.\n\n"
        "3. Stone Throne\n"
        "It is used only in a critical situation."
    )
    out = _enforce_paragraph_evidence(query, answer, chunks)
    assert "1. Guard Sign" in out
    assert "3. Stone Throne" in out
    assert "2. Chain of Wards" not in out


def test_ensure_topn_breadth_rebuilds_list_from_notes_when_too_short():
    query = "give top 5 spells"
    answer = (
        "Confirmed items: 2 of 5.\n\n"
        "1. Stone Throne is a very strong spell.\n\n"
        "2. An unknown spell of an evil wizard."
    )
    chunks = [
        {"text": "Guard Sign is easy to create through a guarding incantation.", "_score": 0.9},
        {"text": "Rabbaar Drobdt curse requires dark magic and experience.", "_score": 0.8},
        {"text": "Stone Throne is used only in a critical situation.", "_score": 0.8},
        {"text": "Necromancer spell is connected with raising the dead.", "_score": 0.7},
        {"text": "Giant weapon gives enormous combat power.", "_score": 0.7},
    ]
    out = _ensure_topn_breadth(query, answer, chunks, 5)
    assert _count_numbered_items(out) >= 5


def test_build_topn_answer_builds_readable_numbered_items(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            '{"items":['
            '{"title":"Guard Sign","summary":"Used to block a passage and protect the entrance.","evidence":[1]},'
            '{"title":"Stone Throne","summary":"Used only in a critical situation.","evidence":[2]}'
            '] }',
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    chunks = [
        {"text": "Guard Sign is used to block a passage and protect the entrance.", "_score": 0.9},
        {"text": "Stone Throne is used only in a critical situation.", "_score": 0.8},
    ]
    out = _build_topn_answer(
        "give top 5 spells",
        chunks,
        req_top_n=5,
        api_base="http://x",
        token="t",
        chat_model="m",
        temperature=0.2,
        max_tokens=700,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "1. Guard Sign" in out
    assert "2. Stone Throne" in out


def test_should_not_replace_healthy_topn_answer_with_composer_output():
    query = "give top 5 strongest spells and how to cast them"
    current = (
        "1. Guard Sign [1][2]\n\n"
        "It is a simple but effective protection spell.\n\n"
        "2. Chain of Wards [2][3]\n\n"
        "It layers several defensive charms.\n\n"
        "3. Stone Throne [3][4]\n\n"
        "It is reserved for critical situations.\n\n"
        "4. Necromancer Spell [4]\n\n"
        "It requires extreme caution."
    )
    candidate = (
        "1. A hero twisted a long branch and blocked the entrance.[1]\n\n"
        "2. Someone knew many awful creations that gathered bloody harvests.[1]"
    )
    assert _should_replace_with_topn_answer(
        query,
        current,
        candidate,
        requested_n=5,
        chunks=[{"text": "x"}],
    ) is False


def test_should_replace_weak_topn_answer_with_composer_output():
    query = "give top 5 strongest spells and how to cast them"
    current = "Not enough confirmed points in the knowledge base for this request."
    candidate = (
        "1. Guard Sign [1]\n\n"
        "Simple barrier spell.\n\n"
        "2. Stone Throne [2]\n\n"
        "Used only in critical situations.\n\n"
        "3. Giant Mark [3]\n\n"
        "Redirects the attack of a powerful giant.\n\n"
        "4. Necromancer Spell [4]\n\n"
        "Connected with raising the dead.\n\n"
        "5. Rabbaar Drobdt Curse [5]\n\n"
        "Requires dark magic knowledge."
    )
    assert _should_replace_with_topn_answer(
        query,
        current,
        candidate,
        requested_n=5,
        chunks=[{"text": "x"}],
    ) is True


def test_build_kb_answer_messages_for_topn_relaxes_refusal_and_sets_shape():
    system_text, user_content = _build_kb_answer_messages(
        query="give top 5 spells",
        numbered_context="[1] spell one\n\n[2] spell two",
        req_top_n=5,
        mode="answer",
        show_sources=True,
        sources_format="list",
        system_prompt_extra="",
        history="",
        follow_up=False,
        use_history=True,
        answer_profile="list",
        answer_style="balanced",
    )
    assert "5" in system_text
    assert "\u0441\u043f\u0438\u0441\u043e\u043a \u0438\u043b\u0438 \u0442\u043e\u043f" in system_text
    assert "5" in user_content


def test_build_kb_answer_messages_for_broad_query_requests_richer_answer():
    system_text, _user_content = _build_kb_answer_messages(
        query="\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438 \u043f\u0440\u043e \u0442\u0430\u0432\u0438 \u0438 \u0435\u0435 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432",
        numbered_context="[1] \u0444\u0430\u043a\u0442 \u043e\u0434\u0438\u043d\n\n[2] \u0444\u0430\u043a\u0442 \u0434\u0432\u0430",
        req_top_n=None,
        mode="answer",
        show_sources=True,
        sources_format="list",
        system_prompt_extra="",
        history="",
        follow_up=False,
        use_history=True,
        answer_profile="overview",
        answer_style="detailed",
    )
    assert "\u0441\u0432\u044f\u0437\u043d\u044b\u0439 \u043e\u0431\u0437\u043e\u0440" in system_text
    assert "\u041d\u0435 \u043f\u0440\u0438\u0434\u0443\u043c\u044b\u0432\u0430\u0439 \u043d\u043e\u0432\u044b\u0445 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0435\u0439" in system_text
    assert "\u0431\u043e\u043b\u0435\u0435 \u0440\u0430\u0437\u0432\u0435\u0440\u043d\u0443\u0442\u044b\u0439" in system_text


def test_build_kb_answer_messages_for_instruction_profile_adds_steps_guidance():
    system_text, _user_content = _build_kb_answer_messages(
        query="\u043a\u0430\u043a \u043d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0431\u0430\u0437\u0435 \u0437\u043d\u0430\u043d\u0438\u0439",
        numbered_context="[1] \u0448\u0430\u0433 \u043e\u0434\u0438\u043d\n\n[2] \u0448\u0430\u0433 \u0434\u0432\u0430",
        req_top_n=None,
        mode="answer",
        show_sources=True,
        sources_format="list",
        system_prompt_extra="",
        history="",
        follow_up=False,
        use_history=True,
        answer_profile="instruction",
        answer_style="balanced",
    )
    assert "\u043f\u043e\u0440\u044f\u0434\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439" in system_text
    assert "\u0448\u0430\u0433\u0438 1), 2), 3)" in system_text


def test_build_kb_answer_messages_for_concise_style_requests_compact_answer():
    system_text, _user_content = _build_kb_answer_messages(
        query="\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0432\u0435\u0441\u0438\u0442 \u0430\u043d\u0442\u0438-\u0442\u0440\u0435\u043d\u0435\u0440",
        numbered_context="[1] 180 \u043a\u0433",
        req_top_n=None,
        mode="answer",
        show_sources=True,
        sources_format="short",
        system_prompt_extra="",
        history="",
        follow_up=False,
        use_history=True,
        answer_profile="fact",
        answer_style="concise",
    )
    assert "\u043a\u043e\u043c\u043f\u0430\u043a\u0442\u043d\u044b\u043c" in system_text


def test_build_entity_list_answer_returns_structured_list(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            '{"items":['
            '{"title":"Ondulast Spell","summary":"A complex spell that requires concentration.","instruction":"Cast it carefully and avoid detection.","evidence":[1]},'
            '{"title":"Tavi Guard Spell","summary":"A protective barrier that hides the entrance.","instruction":"Use it to conceal the path into the valley.","evidence":[2]}'
            '] }',
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    chunks = [
        {"text": "Ondulast spell is complex and requires concentration to avoid detection.", "_score": 0.9},
        {"text": "Tavi guard spell hides the entrance into the valley.", "_score": 0.8},
    ]
    out = _build_entity_list_answer(
        "give top 5 strongest spells and how to cast them",
        chunks,
        req_top_n=5,
        api_base="http://x",
        token="t",
        chat_model="m",
        temperature=0.2,
        max_tokens=700,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "1. Ondulast Spell" in out
    assert "Tavi Guard Spell" in out
    assert "Как создать или применить" in out


def test_should_replace_with_entity_list_answer_when_current_is_overcautious():
    current = (
        "There is not enough complete information to produce an exact top 5, "
        "but a few examples are known.\n\n"
        "1. Some spell\n"
        "2. Another spell"
    )
    candidate = (
        "1. Ondulast Spell\n\nA complex spell.\n\n"
        "2. Tavi Guard Spell\n\nA protective barrier.\n\n"
        "3. Stone Throne Sign\n\nUsed in a critical situation.\n\n"
        "4. Giant Mark\n\nA mark tied to giant power."
    )
    assert _should_replace_with_entity_list_answer(
        "give top 5 strongest spells and how to cast them",
        current,
        candidate,
        requested_n=5,
        chunks=[{"text": "x"}],
    ) is True


def test_strip_topn_caveat_paragraphs_removes_intro_and_outro_when_list_is_present():
    answer = (
        "Хотя достоверной информации о пятерке наиболее могущественных заклинаний недостаточно, "
        "мы можем рассмотреть несколько известных примеров.\n\n"
        "1. Guard Sign\n\n"
        "A powerful defensive spell.\n\n"
        "2. Ondulast Spell\n\n"
        "A complex spell that requires concentration.\n\n"
        "3. Stone Throne Sign\n\n"
        "A last-resort sign used in a critical situation.\n\n"
        "Чтобы сформировать полноценный список сильнейших заклинаний, необходимы дополнительные сведения."
    )
    out = _strip_topn_caveat_paragraphs(answer, 5)
    assert "Хотя достоверной информации" not in out
    assert "Чтобы сформировать полноценный список" not in out
    assert "1. Guard Sign" in out
    assert "3. Stone Throne Sign" in out


def test_strip_topn_caveat_paragraphs_keeps_non_list_answer_unchanged():
    answer = "Данных недостаточно для подтвержденного ответа."
    assert _strip_topn_caveat_paragraphs(answer, 5) == answer


def test_style_rewrite_topn_answer_preserves_numbered_shape(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            "1. Guard Sign\n"
            "A simple and effective protective spell.\n\n"
            "2. Stone Throne\n"
            "A last-resort sign used only in a critical situation.",
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _style_rewrite_topn_answer(
        query="give top 5 spells",
        factual_answer=(
            "1. Guard Sign\n"
            "It is simple.\n\n"
            "2. Stone Throne\n"
            "It is used only in a critical situation."
        ),
        requested_n=5,
        chunks=[{"text": "Guard Sign protects the entrance."}, {"text": "Stone Throne is last-resort."}],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "1. Guard Sign" in out
    assert "2. Stone Throne" in out


def test_expand_short_grounded_answer_returns_richer_text(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            "Тави вместе со спутниками пробирается через опасные болота, где им постоянно угрожает Ливень.\n\n"
            "По подтвержденным фрагментам видно, что рядом с ней есть спутники, а сама ситуация связана с тяжелым переходом, "
            "магической угрозой и необходимостью действовать осторожно.",
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _expand_short_grounded_answer(
        query="расскажи про тави и ее спутников",
        factual_answer="Тави вместе со спутниками идет через болота.",
        chunks=[
            {"text": "Тави и ее спутники идут через болота, где им угрожает Ливень."},
            {"text": "Им приходится действовать осторожно и искать безопасный путь."},
            {"text": "Ситуация осложняется магической угрозой и преследованием."},
        ],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "болота" in out.lower()
    assert "спутник" in out.lower()


def test_expand_short_grounded_answer_rejects_new_unseen_name(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return "Тави идет через болота вместе с Мариком и другими спутниками.", None, {}

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _expand_short_grounded_answer(
        query="расскажи про тави и ее спутников",
        factual_answer="Тави вместе со спутниками идет через болота.",
        chunks=[
            {"text": "Тави и ее спутники идут через болота, где им угрожает Ливень."},
            {"text": "Им приходится действовать осторожно и искать безопасный путь."},
            {"text": "Ситуация осложняется магической угрозой и преследованием."},
        ],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is None


def test_build_grounded_instruction_answer_returns_grounded_steps(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            "1) Откройте раздел пользователей и прав.\n"
            "2) Выберите нужного пользователя и назначьте доступ.\n"
            "3) Сохраните изменения.",
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _build_grounded_instruction_answer(
        query="как настроить доступ к базе знаний",
        chunks=[
            {"text": "Откройте раздел пользователей и прав, затем выберите пользователя."},
            {"text": "Назначьте доступ к базе знаний и сохраните изменения."},
        ],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "1)" in out and "2)" in out and "3)" in out


def test_is_product_settings_query_detects_product_access_questions():
    assert _is_product_settings_query("как настроить доступ к базе знаний")
    assert _is_product_settings_query("где находится раздел пользователи и права")
    assert not _is_product_settings_query("расскажи про тави и ее спутников")


def test_build_grounded_instruction_answer_adds_product_guard(monkeypatch):
    captured = {}

    def _fake_chat_complete(_api, _token, _model, messages, **kwargs):
        captured["system"] = messages[0]["content"]
        return "1) Откройте раздел пользователей и прав. 2) Назначьте доступ.", None, {}

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _build_grounded_instruction_answer(
        query="как настроить доступ к базе знаний",
        chunks=[
            {"text": "Откройте раздел пользователей и прав."},
            {"text": "Назначьте доступ к базе знаний и сохраните изменения."},
        ],
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "общими советами по организации документов" in captured["system"]


def test_build_grounded_windows_keeps_neighboring_sentences_for_broad_query():
    out = _build_grounded_windows(
        "расскажи про тави и ее спутников",
        [
            {
                "text": (
                    "Тави вместе со спутниками пробирается через болота. "
                    "Им приходится искать безопасный путь и действовать осторожно. "
                    "Позади движется Ливень."
                ),
                "filename": "chapter.fb2",
                "file_summary": "История про Тави и опасный путь через болота.",
                "_score": 0.7,
            }
        ],
        limit=4,
        neighbor_radius=1,
    )
    assert out
    joined = " ".join(out).lower()
    assert "болота" in joined
    assert "безопасный путь" in joined
    assert "тави" in joined


def test_build_grounded_overview_answer_rejects_numbered_or_hallucinated_output(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            "1. Тави ведет отряд вперед.\n"
            "2. Марик помогает ей в пути.",
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _build_grounded_overview_answer(
        query="расскажи про тави и ее спутников",
        chunks=[
            {"text": "Тави и ее спутники идут через болота, где им угрожает Ливень."},
            {"text": "Им приходится действовать осторожно и искать безопасный путь."},
            {"text": "Ситуация осложняется магической угрозой и преследованием."},
        ],
        current_answer="Тави вместе со спутниками идет через болота.",
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is None


def test_build_grounded_overview_answer_accepts_richer_grounded_overview(monkeypatch):
    def _fake_chat_complete(*args, **kwargs):
        return (
            "Тави вместе со спутниками пробирается через опасные болота, где им угрожает Ливень и другие опасности.\n\n"
            "По подтвержденным фрагментам видно, что им приходится двигаться осторожно, искать безопасный путь и действовать под постоянным давлением."
            ,
            None,
            {},
        )

    monkeypatch.setattr("apps.backend.services.kb_rag.chat_complete", _fake_chat_complete)
    out = _build_grounded_overview_answer(
        query="расскажи про тави и ее спутников",
        chunks=[
            {"text": "Тави и ее спутники идут через болота, где им угрожает Ливень."},
            {"text": "Им приходится действовать осторожно и искать безопасный путь."},
            {"text": "Ситуация осложняется магической угрозой и преследованием."},
        ],
        current_answer="Тави вместе со спутниками идет через болота.",
        api_base="http://x",
        token="t",
        chat_model="m",
        max_tokens=900,
        top_p=0.9,
        presence_penalty=0,
        frequency_penalty=0,
    )
    assert out is not None
    assert "болота" in out.lower()
    assert "ливень" in out.lower()


def test_rerank_candidates_prefers_keyword_evidence_for_list_intent():
    candidates = [
        {
            "chunk_id": 1,
            "_score": 0.92,
            "text": "Общее описание битвы без конкретных заклинаний.",
            "filename": "book.fb2",
            "source_title": "",
            "source_url": "",
            "file_summary": "",
        },
        {
            "chunk_id": 2,
            "_score": 0.73,
            "text": "Охранное заклинание закрывает вход. Каменный Престол применяют в критической ситуации.",
            "filename": "zaklinaniya.fb2",
            "source_title": "",
            "source_url": "",
            "file_summary": "Список важных заклинаний и знаков",
        },
    ]
    out = _rerank_candidates("дай топ 5 сильных заклинаний", candidates, top_k=2, list_intent=True)
    assert out
    assert out[0]["chunk_id"] == 2
