import json
import os
from types import SimpleNamespace
from unittest import mock

import httpx
import openai
from django.test import SimpleTestCase
from pydantic import ValidationError

from PGAI.services import llm
from PGAI.services.prompts import (
    CONCEPT_SYSTEM_PROMPT,
    EXERCISE_SYSTEM_PROMPT,
    FLASHCARD_SYSTEM_PROMPT,
)
from PGAI.services.schemas import Exercicio, Flashcards, Resumo, json_schema, response_format


EXERCISE = {
    "pergunta": "Qual é a unidade de tensão?",
    "alternativas": [
        {"letra": "A", "texto": "Volt"},
        {"letra": "B", "texto": "Ohm"},
        {"letra": "C", "texto": "Ampère"},
        {"letra": "D", "texto": "Watt"},
    ],
    "correta": "A",
    "explicacao": "A tensão é medida em volts.",
}


def api_error(error_class, status, message="erro"):
    request = httpx.Request("POST", llm.GEMINI_BASE_URL)
    response = httpx.Response(status, request=request, json={"error": {"message": message}})
    return error_class(message, response=response, body=None)


def api_response(content):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class SchemaTests(SimpleTestCase):
    def test_exercise_accepts_valid_data(self):
        exercise = Exercicio.model_validate(EXERCISE)
        self.assertEqual(exercise.correta, "A")
        self.assertEqual(len(exercise.alternativas), 4)

    def test_exercise_sorts_alternatives(self):
        data = {**EXERCISE, "alternativas": list(reversed(EXERCISE["alternativas"]))}
        exercise = Exercicio.model_validate(data)
        self.assertEqual([a.letra for a in exercise.alternativas], ["A", "B", "C", "D"])

    def test_exercise_rejects_incomplete_data(self):
        invalid = [
            {k: v for k, v in EXERCISE.items() if k != "explicacao"},
            {**EXERCISE, "correta": "E"},
            {**EXERCISE, "pergunta": "   "},
            {**EXERCISE, "alternativas": EXERCISE["alternativas"][:3]},
            {**EXERCISE, "alternativas": [EXERCISE["alternativas"][0]] * 4},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                Exercicio.model_validate(data)

    def test_flashcards_limits(self):
        card = {"frente": "Pergunta", "verso": "Resposta"}
        self.assertEqual(len(Flashcards.model_validate({"cards": [card] * 5}).cards), 5)
        for cards in ([], [card] * 6, [{"frente": "Pergunta"}]):
            with self.subTest(cards=cards), self.assertRaises(ValidationError):
                Flashcards.model_validate({"cards": cards})

    def test_resumo_rejects_empty_section(self):
        section = {"titulo": "Definição", "paragrafos": [], "itens": [], "bloco": "  \n"}
        with self.assertRaises(ValidationError):
            Resumo.model_validate({"titulo": "Lei de Ohm", "secoes": [section]})

    def test_block_keeps_diagram_indentation(self):
        section = {"titulo": "Circuito", "paragrafos": [], "itens": [], "bloco": "\n  +--+\n  |  |\n"}
        resumo = Resumo.model_validate({"titulo": "Lei de Ohm", "secoes": [section]})
        self.assertEqual(resumo.secoes[0].bloco, "  +--+\n  |  |")

    def test_json_schema_has_no_refs(self):
        for schema in (Exercicio, Flashcards, Resumo):
            with self.subTest(schema=schema.__name__):
                text = json.dumps(json_schema(schema))
                self.assertNotIn("$ref", text)
                self.assertNotIn("$defs", text)

    def test_json_schema_limits_items(self):
        schema = json_schema(Exercicio)["properties"]["alternativas"]
        self.assertEqual((schema["minItems"], schema["maxItems"]), (4, 4))
        self.assertEqual(schema["items"]["properties"]["letra"]["enum"], ["A", "B", "C", "D"])

    def test_response_format_uses_json_schema(self):
        result = response_format(Flashcards)
        self.assertEqual(result["type"], "json_schema")
        self.assertEqual(result["json_schema"]["name"], "Flashcards")


class PromptTests(SimpleTestCase):
    def test_prompts_have_no_delimiter_rules(self):
        for prompt in (CONCEPT_SYSTEM_PROMPT, FLASHCARD_SYSTEM_PROMPT, EXERCISE_SYSTEM_PROMPT):
            with self.subTest(prompt=prompt[:40]):
                for delimiter in ("$", "#", "|"):
                    self.assertNotIn(delimiter, prompt)
                self.assertIn("sempre com acentos e cedilha", prompt)
                self.assertIn("Não use LaTeX", prompt)
                self.assertIn("V = R * I", prompt)


@mock.patch.dict(os.environ, {"LLM_MOCK": "1"})
@mock.patch.object(llm, "MOCK_DELAY_SECONDS", 0)
@mock.patch.object(llm, "_client", side_effect=AssertionError("o modo mock não pode usar a API"))
class MockModeTests(SimpleTestCase):
    def test_fixtures_are_valid(self, _client):
        self.assertEqual(llm.explain_concept("Lei de Ohm").titulo, "Lei de Ohm")
        self.assertEqual(llm.generate_exercise("Lei de Ohm").correta, "B")
        self.assertEqual(len(llm.generate_flashcards("Lei de Ohm", 5)), 5)

    def test_flashcards_respect_quantity(self, _client):
        self.assertEqual(len(llm.generate_flashcards("Lei de Ohm", 2)), 2)

    def test_invalid_fixtures_raise_clear_error(self, _client):
        for generate in (llm.explain_concept, llm.generate_exercise, llm.generate_flashcards):
            with self.subTest(generate=generate.__name__), self.assertRaises(llm.InvalidResponse):
                generate("mock:invalido")

    def test_simulated_failures(self, _client):
        with self.assertRaises(llm.RateLimitExceeded):
            llm.generate_exercise("mock:429")
        with self.assertRaises(llm.ServiceUnavailable):
            llm.explain_concept("mock:503")


@mock.patch.dict(os.environ, {"LLM_MOCK": "0"})
class RealModeTests(SimpleTestCase):
    def setUp(self):
        llm._rejected_schemas.clear()
        self.addCleanup(llm._rejected_schemas.clear)
        patcher = mock.patch.object(llm, "_client")
        self.create = patcher.start().return_value.chat.completions.create
        self.addCleanup(patcher.stop)

    def test_client_uses_one_retry(self):
        mock.patch.stopall()
        llm._client.cache_clear()
        self.addCleanup(llm._client.cache_clear)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "chave-de-teste"}):
            self.assertEqual(llm._client().max_retries, 1)

    def test_sends_json_schema(self):
        self.create.return_value = api_response(json.dumps(EXERCISE))
        exercise = llm.generate_exercise("Lei de Ohm")
        self.assertEqual(exercise.pergunta, EXERCISE["pergunta"])
        self.create.assert_called_once()
        kwargs = self.create.call_args.kwargs
        self.assertEqual(kwargs["response_format"], response_format(Exercicio))
        self.assertEqual(kwargs["temperature"], 1)

    def test_falls_back_to_prompt_when_schema_is_rejected(self):
        self.create.side_effect = [
            api_error(openai.BadRequestError, 400, "Invalid schema"),
            api_response("```json\n" + json.dumps(EXERCISE) + "\n```"),
        ]
        exercise = llm.generate_exercise("Lei de Ohm")
        self.assertEqual(exercise.correta, "A")
        self.assertEqual(self.create.call_count, 2)
        retry = self.create.call_args.kwargs
        self.assertNotIn("response_format", retry)
        self.assertEqual(retry["temperature"], 1)
        self.assertIn('"alternativas"', retry["messages"][0]["content"])

    def test_rejected_schema_is_not_requested_again(self):
        self.create.side_effect = [
            api_error(openai.BadRequestError, 400, "Invalid schema"),
            api_response(json.dumps(EXERCISE)),
            api_response(json.dumps(EXERCISE)),
        ]
        llm.generate_exercise("Lei de Ohm")
        llm.generate_exercise("Lei de Ohm")
        self.assertEqual(self.create.call_count, 3)
        self.assertNotIn("response_format", self.create.call_args.kwargs)

    def test_invalid_api_key_does_not_trigger_fallback(self):
        self.create.side_effect = api_error(openai.BadRequestError, 400, "API key not valid.")
        with self.assertRaises(llm.LLMError) as context:
            llm.generate_exercise("Lei de Ohm")
        self.assertIs(type(context.exception), llm.LLMError)
        self.create.assert_called_once()

    def test_invalid_fallback_response_raises_clear_error(self):
        self.create.side_effect = [
            api_error(openai.BadRequestError, 400, "Invalid schema"),
            api_response('{"pergunta": "incompleta"'),
        ]
        with self.assertRaises(llm.InvalidResponse):
            llm.generate_exercise("Lei de Ohm")

    def test_truncated_or_empty_response_raises_clear_error(self):
        for content in ('{"pergunta": "Qual é', "", None):
            with self.subTest(content=content):
                self.create.return_value = api_response(content)
                with self.assertRaises(llm.InvalidResponse):
                    llm.generate_exercise("Lei de Ohm")

    def test_response_without_choices_raises_clear_error(self):
        self.create.return_value = SimpleNamespace(choices=None)
        with self.assertRaises(llm.InvalidResponse):
            llm.explain_concept("Lei de Ohm")

    def test_rate_limit_maps_to_friendly_error(self):
        self.create.side_effect = api_error(openai.RateLimitError, 429)
        with self.assertRaises(llm.RateLimitExceeded) as context:
            llm.generate_flashcards("Lei de Ohm")
        self.assertEqual(context.exception.status, 429)

    def test_unavailable_maps_to_friendly_error(self):
        request = httpx.Request("POST", llm.GEMINI_BASE_URL)
        failures = [
            api_error(openai.InternalServerError, 503),
            openai.APIConnectionError(request=request),
            openai.APITimeoutError(request=request),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                self.create.side_effect = failure
                with self.assertRaises(llm.ServiceUnavailable) as context:
                    llm.explain_concept("Lei de Ohm")
                self.assertEqual(context.exception.status, 503)

    def test_other_api_errors_do_not_expose_details(self):
        self.create.side_effect = api_error(openai.NotFoundError, 404, "detalhe interno")
        with self.assertRaises(llm.LLMError) as context:
            llm.explain_concept("Lei de Ohm")
        self.assertNotIn("detalhe interno", str(context.exception))
