import os
from unittest import mock

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

from PGAI.services import llm
from PGAI.services.schemas import Flashcards


@mock.patch.dict(os.environ, {"LLM_MOCK": "1"})
@mock.patch.object(llm, "MOCK_DELAY_SECONDS", 0)
@mock.patch.object(llm, "_client", side_effect=AssertionError("o modo mock não pode usar a API"))
class ViewTests(SimpleTestCase):
    def test_pages_load(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_typed_routes_redirect_to_trailing_slash(self, _client):
        for url in ("/flashcards", "/exercicios"):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{url}/", status_code=301)

    def test_navigation_marks_current_page(self, _client):
        response = self.client.get("/exercicios/")
        self.assertContains(response, 'aria-current="page"', count=1)
        self.assertContains(response, 'href="/exercicios/" aria-current="page"')

    def test_static_files_are_found(self, _client):
        self.assertIsNotNone(finders.find("css/app.css"))
        self.assertIsNotNone(finders.find("js/app.js"))

    def test_summary_renders_sections(self, _client):
        response = self.client.post("/", {"user_prompt": "Lei de Ohm"})
        self.assertContains(response, "<h1>Lei de Ohm</h1>", html=True)
        self.assertContains(response, "Cálculo passo a passo")
        self.assertContains(response, "<li>Isole a corrente: I = V / R.</li>", html=True)
        self.assertContains(response, "<pre>V = R * I</pre>", html=True)

    def test_summary_escapes_model_output(self, _client):
        response = self.client.post("/", {"user_prompt": "Lei de Ohm"})
        self.assertContains(response, "Símbolos como &lt; e &amp; aparecem")

    def test_responses_have_no_prefix(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                response = self.client.post(url, {"user_prompt": "Lei de Ohm"})
                self.assertNotContains(response, "PG:")
                self.assertNotContains(response, "Pergunta:")

    def test_flashcards_render_requested_quantity(self, _client):
        response = self.client.post("/flashcards/", {"user_prompt": "Lei de Ohm", "quantity": "2"})
        self.assertContains(response, "data-card", count=2)
        self.assertContains(response, "1 de 2")
        self.assertContains(response, '<option value="2" selected>2</option>', html=True)

    def test_single_flashcard_has_no_navigation(self, _client):
        response = self.client.post("/flashcards/", {"user_prompt": "Lei de Ohm", "quantity": "1"})
        self.assertContains(response, "data-card", count=1)
        self.assertNotContains(response, "data-next")

    def test_flashcard_quantity_is_limited(self, _client):
        for quantity, expected in (("0", 1), ("9", 5), ("abc", 3), ("", 3)):
            with self.subTest(quantity=quantity):
                with mock.patch.object(llm, "generate_flashcards", wraps=llm.generate_flashcards) as generate:
                    self.client.post("/flashcards/", {"user_prompt": "Lei de Ohm", "quantity": quantity})
                generate.assert_called_once_with("Lei de Ohm", expected)

    def test_flashcards_with_no_quantity_use_default(self, _client):
        response = self.client.post("/flashcards/", {"user_prompt": "Lei de Ohm"})
        self.assertContains(response, "data-card", count=3)

    def test_exercise_renders_full_alternatives(self, _client):
        response = self.client.post("/exercicios/", {"user_prompt": "Lei de Ohm"})
        self.assertContains(response, 'data-correct="B"')
        self.assertContains(response, "data-option=", count=4)
        self.assertContains(response, "que é sempre desprezada nos cálculos.")
        self.assertContains(response, "Pela Lei de Ohm, I = V / R")

    def test_invalid_response_shows_clear_error(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                response = self.client.post(url, {"user_prompt": "mock:invalido"})
                self.assertContains(response, llm.InvalidResponse.message, status_code=502)
                self.assertContains(response, 'role="alert"', status_code=502)
                self.assertNotContains(response, "não encontrada", status_code=502)

    def test_rate_limit_shows_friendly_error(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                response = self.client.post(url, {"user_prompt": "mock:429"})
                self.assertContains(response, "Limite de requisições atingido", status_code=429)

    def test_unavailable_shows_friendly_error(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                response = self.client.post(url, {"user_prompt": "mock:503"})
                self.assertContains(response, "indisponível no momento", status_code=503)

    def test_empty_prompt_shows_error_without_generating(self, _client):
        for url in ("/", "/flashcards/", "/exercicios/"):
            with self.subTest(url=url):
                with mock.patch.object(llm, "_generate") as generate:
                    response = self.client.post(url, {"user_prompt": "   "})
                self.assertContains(response, "Por favor, forneça um prompt.", status_code=400)
                generate.assert_not_called()

    def test_prompt_stays_in_form_and_is_escaped(self, _client):
        response = self.client.post("/exercicios/", {"user_prompt": "<script>alert(1)</script>"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_html_in_model_output_is_not_rendered(self, _client):
        cards = Flashcards.model_validate({"cards": [{"frente": "<b>a</b>", "verso": "<i>b</i>"}]}).cards
        with mock.patch.object(llm, "generate_flashcards", return_value=cards):
            response = self.client.post("/flashcards/", {"user_prompt": "Lei de Ohm"})
        self.assertNotContains(response, "<b>a</b>")
        self.assertContains(response, "&lt;b&gt;a&lt;/b&gt;")
