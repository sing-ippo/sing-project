import pytest
from fastapi.testclient import TestClient

from voice_server import app 

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_check(client: TestClient):
    """Проверка, что сервер вообще живой"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ask_endpoint_wav_file(client: TestClient):
    """
        Тест для распознавания WAV-файлов
        1. Отправка WAV-файла
        2. Проверка наличия полей: question, answer, audio_base64
    """
    wav_paths = ["test_audios/лабы.wav", "test_audios/расписание.wav"]
    
    for i in wav_paths:
        with open(i, "rb") as f:
            response = client.post(
                "/ask",
                files={"file": ("test_audio.wav", f, "audio/wav")}
            )

        assert response.status_code == 200, f"Ошибка сервера: {response.text}"
        
        data = response.json()
        
        # Проверка наличия обязательных полей
        assert "question" in data
        assert "answer" in data
        assert "audio_base64" in data
        
        # Проверка, что данные не пустые
        assert len(data["question"]) > 0
        assert len(data["answer"]) > 0
        assert len(data["audio_base64"]) > 100 # Минимум данных в base64

        print(f"--- Результат для файла: {i} ---")
        print("Вопрос, полученный из аудио:", f"`{data["question"]}`")
        print("Ответ, сформированный на основе вопроса: ", f"`{data["answer"]}`")

def test_ask_endpoint_wav_file_silence(client: TestClient):
    """
        Тест для проверки отправки пустого WAV-файла (тишина) и получения ошибки сервера 400.
    """
    wav_path = "test_audios/тишина.wav"
    with open(wav_path, 'rb') as file:
        response = client.post("/ask", files={"file": ("test_audio.wav", file, "audio/wav")})
    
    assert response.status_code == 400

    print(f"--- Результат для файла: {wav_path} ---")
    print(response.json())

def test_ask_endpoint_webm_file(client: TestClient):
    """
        Тест для распознавания WEBM-файлов
        1. Отправка WEBM-файла
        2. Проверка наличия полей: question, answer, audio_base64
    """

    webm_path = "test_audios/учебный_отдел.webm"
    with open(webm_path, "rb") as file:
        response = client.post(
            "/ask",
            files={"file": ("test_audio.webm", file, "audio/webm")}
        )

    assert response.status_code == 200, f"Ошибка сервера: {response.text}"

    data = response.json()

    assert "question" in data
    assert "answer" in data
    assert "audio_base64" in data

    assert len(data["question"]) > 0
    assert len(data["answer"]) > 0
    assert len(data["audio_base64"]) > 100

    print(f"--- Результат для файла: {webm_path} ---")
    print("Вопрос, полученный из аудио:", f"`{data["question"]}`")
    print("Ответ, сформированный на основе вопроса: ", f"`{data["answer"]}`")