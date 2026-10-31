import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import ValidationError

from .prompts import (
    CONCEPT_SYSTEM_PROMPT,
    EXERCISE_SYSTEM_PROMPT,
    EXERCISE_USER_TEMPLATE,
    FLASHCARD_SYSTEM_PROMPT,
    FLASHCARD_USER_TEMPLATE,
    JSON_FALLBACK_INSTRUCTION,
)
from .schemas import Exercicio, Flashcards, Resumo, json_schema, response_format

logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Modelo usado por todas as funcionalidades (LLM_MODEL vazio também usa o padrão)
MODEL = os.getenv("LLM_MODEL") or "gemini-3.8-flash"

# Modo mock: LLM_MOCK=1 troca a API pelas respostas em services/fixtures/
FIXTURES_DIR = Path(__file__).parent / "fixtures"
MOCK_DELAY_SECONDS = 1

# Schemas que o endpoint rejeitou nesta execução; evita gastar uma requisição a cada envio
_rejected_schemas = set()


# Erros exibidos na tela: cada classe traz a mensagem e o status HTTP da página
class LLMError(Exception):
    status = 502
    message = "Não foi possível gerar a resposta. Confira a configuração da API e tente novamente."

    def __str__(self):
        return self.message


class RateLimitExceeded(LLMError):
    status = 429
    message = (
        "Limite de requisições atingido. Aguarde um minuto e tente novamente. "
        "Se o aviso continuar, a cota diária acabou e será renovada à meia-noite do horário do Pacífico."
    )


class ServiceUnavailable(LLMError):
    status = 503
    message = "O Gemini está indisponível no momento. Tente novamente em alguns minutos."


class InvalidResponse(LLMError):
    message = "O modelo enviou uma resposta inválida ou incompleta. Tente gerar novamente."


# O cliente só é criado na primeira chamada real, então o modo mock dispensa a chave
@lru_cache(maxsize=1)
def _client():
    return OpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url=GEMINI_BASE_URL, max_retries=1)


def _mock_enabled():
    return os.getenv("LLM_MOCK") == "1"


def _mock_response(schema, user_content):
    """Lê a fixture do schema. "mock:429", "mock:503" e "mock:invalido" no texto simulam falhas."""
    time.sleep(MOCK_DELAY_SECONDS)
    if "mock:429" in user_content:
        raise RateLimitExceeded()
    if "mock:503" in user_content:
        raise ServiceUnavailable()
    suffix = "_invalido" if "mock:invalido" in user_content else ""
    return (FIXTURES_DIR / f"{schema.__name__.lower()}{suffix}.json").read_text(encoding="utf-8")


def _chat(system_prompt, user_content, **params):
    """Faz uma única chamada de chat (sem histórico) e retorna o texto da resposta."""
    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        **params
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""


def _strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return text


def _request_json(schema, system_prompt, user_content, **params):
    """Pede a resposta com json_schema; se o endpoint rejeitar, pede o JSON no prompt."""
    if schema not in _rejected_schemas:
        try:
            return _chat(system_prompt, user_content, response_format=response_format(schema), **params)
        except BadRequestError as e:
            # O Gemini também responde 400 para chave inválida, que não se resolve com o fallback
            if "api key" in str(e).lower():
                raise
            logger.warning("json_schema rejeitado para %s: %s", schema.__name__, e)
            _rejected_schemas.add(schema)

    instruction = JSON_FALLBACK_INSTRUCTION.format(
        schema=json.dumps(json_schema(schema), ensure_ascii=False)
    )
    return _strip_code_fence(_chat(system_prompt + instruction, user_content, **params))


def _generate(schema, system_prompt, user_content, **params):
    """Obtém a resposta do modelo e a valida; toda falha vira um LLMError com mensagem para a tela."""
    try:
        if _mock_enabled():
            raw = _mock_response(schema, user_content)
        else:
            raw = _request_json(schema, system_prompt, user_content, **params)
        return schema.model_validate_json(raw)
    except ValidationError as e:
        logger.warning("Resposta inválida para %s: %s", schema.__name__, e)
        raise InvalidResponse() from e
    except RateLimitError as e:
        raise RateLimitExceeded() from e
    except (InternalServerError, APIConnectionError) as e:
        raise ServiceUnavailable() from e
    except OpenAIError as e:
        logger.error("Erro na chamada ao modelo: %s", e)
        raise LLMError() from e


# Assistente de engenharia: retorna um Resumo (título e seções)
def explain_concept(prompt):
    return _generate(Resumo, CONCEPT_SYSTEM_PROMPT, prompt)


# Flashcards: retorna uma lista de Flashcard com no máximo `quantity` itens
def generate_flashcards(topic, quantity=3):
    user_content = FLASHCARD_USER_TEMPLATE.format(quantity=quantity, topic=topic)
    return _generate(Flashcards, FLASHCARD_SYSTEM_PROMPT, user_content, temperature=0.7).cards[:quantity]


# Exercícios: retorna um Exercicio (pergunta, 4 alternativas, letra correta e explicação)
def generate_exercise(topic):
    return _generate(
        Exercicio, EXERCISE_SYSTEM_PROMPT, EXERCISE_USER_TEMPLATE.format(topic=topic),
        temperature=1  # Aumenta a variação das perguntas geradas
    )
