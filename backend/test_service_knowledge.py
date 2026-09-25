from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import solution_assistant as assistant
from auth import _digest
from service_knowledge import KNOWLEDGE, answer_service_question


def test_service_questions_cover_navigation_without_catalog_answers():
    examples = {
        "С чего начать оценку роботизации?": "start",
        "Что умеет сервис и чего он не подтверждает?": "capabilities",
        "Какие данные нужны для первого расчёта?": "data",
        "Что такое зона и что писать в этом поле?": "zone",
        "Можно ли начать без цены и без регистрации?": "demo",
        "Как оценить срок окупаемости и NPV?": "economics",
        "Почему мой отчёт частичный?": "partial",
        "Где найти сохранённый отчёт?": "reports",
        "Где посмотреть 2D и 3D?": "visualization",
        "Сколько стоит конкретный робот?": "catalog",
    }
    for question, expected in examples.items():
        answer = answer_service_question(question)
        assert answer["schema_version"] == KNOWLEDGE["version"]
        assert answer["topic_id"] == expected, question
        assert answer["reply"]
        assert all(action["id"] in {"demo", "calculation", "catalog", "projects", "result"}
                   for action in answer["actions"])


def test_unknown_and_robot_specific_question_do_not_invent_model_facts():
    unknown = answer_service_question("Нужен самоподписанный сертификат")
    assert unknown["topic_id"] == "unknown"
    assert "Уточните" in unknown["reply"]
    robot = answer_service_question("Какой робот сам снимает коробки со стеллажей?")
    assert robot["topic_id"] in {"catalog", "unknown"}
    assert "подтверждён" not in robot["reply"].casefold() or "источники" in robot["reply"]


def test_service_route_is_guest_accessible_and_project_scoped(monkeypatch):
    import main

    def fake_session():
        yield SimpleNamespace(scalar=lambda query: None)

    main.app.dependency_overrides[assistant.database_session] = fake_session
    try:
        with TestClient(main.app) as client:
            guest = client.post("/api/assistant/service", json={"message": "С чего начать?"})
            assert guest.status_code == 200
            assert guest.json()["topic_id"] == "start"

            project_id = str(uuid.uuid4())
            project = client.post("/api/assistant/service", json={"message": "С чего начать?", "project_id": project_id})
            assert project.status_code in {401, 403}

            monkeypatch.setattr(assistant, "require_auth_context", lambda request, db: SimpleNamespace(
                user=SimpleNamespace(id=uuid.uuid4()), session=SimpleNamespace(csrf_sha256=""),
            ))
            project = client.post("/api/assistant/service", json={"message": "С чего начать?", "project_id": project_id})
            assert project.status_code == 403

            monkeypatch.setattr(assistant, "require_auth_context", lambda request, db: SimpleNamespace(
                user=SimpleNamespace(id=uuid.uuid4()), session=SimpleNamespace(csrf_sha256=_digest("test-token")),
            ))
            client.cookies.set("robodovod_csrf", "test-token")
            project = client.post("/api/assistant/service", json={"message": "С чего начать?", "project_id": project_id},
                                  headers={"X-CSRF-Token": "test-token"})
            assert project.status_code == 404
    finally:
        main.app.dependency_overrides.pop(assistant.database_session, None)
