import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import (
    CONCEPT_SYSTEM_PROMPT,
    EXERCISE_SYSTEM_PROMPT,
    EXERCISE_USER_TEMPLATE,
    FLASHCARD_SYSTEM_PROMPT,
)

# Carregar variáveis de ambiente
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Modelo usado por todas as funcionalidades
MODEL = "gpt-3.5-turbo"


def _chat(system_prompt, user_content, **params):
    """Faz uma única chamada de chat (sem histórico) e retorna o texto da resposta."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        **params
    )
    return response.choices[0].message.content


# Função para formatar a resposta antes de enviá-la ao template
def format_response(response):
    if not response:
        return "Nenhuma resposta gerada."

    # Adiciona quebras de linha para melhorar a legibilidade
    formatted = response.replace("\n", "<br>")

    # Negrito para palavras-chave importantes
    keywords = ["Definição:", "Exemplo:", "Fórmula:", "Importante:", "Observação:"]
    for word in keywords:
        formatted = formatted.replace(word, f"<strong>{word}</strong>")

    # Convertendo listas para HTML (se detectar "- " no início das linhas)
    formatted = re.sub(r"- (.+)", r"<li>\1</li>", formatted)
    formatted = re.sub(r"(<li>.*?</li>)", r"<ul>\1</ul>", formatted)  # Garante que seja uma lista UL

    # Código e fórmulas (se houver trechos dentro de crases ``)
    formatted = re.sub(r"``(.*?)``", r"<pre><code>\1</code></pre>", formatted)

    return formatted


# Assistente de engenharia: retorna a explicação já formatada em HTML
def explain_concept(prompt):
    try:
        return format_response(_chat(CONCEPT_SYSTEM_PROMPT, prompt))
    except Exception as e:
        return f"Erro ao processar o prompt: {str(e)}"


# Flashcards: retorna {'question', 'answer'} a partir do formato "pergunta | resposta"
def generate_flashcard(topic):
    try:
        raw = _chat(
            FLASHCARD_SYSTEM_PROMPT, topic,
            temperature=0.7,
            frequency_penalty=0,
            presence_penalty=0
        )
    except Exception as e:
        raw = f"Erro ao processar o prompt: {str(e)}"
    return parse_flashcard(raw)


def parse_flashcard(raw):
    # Separa a string usando '|' como delimitador
    if '|' in raw:
        question, answer = raw.split('|', 1)  # Divide apenas no primeiro |
        return {'question': question.strip(), 'answer': answer.strip()}
    # Caso não encontre o separador
    return {'question': raw, 'answer': "Resposta não encontrada"}


# Exercícios: retorna {'question', 'alternatives', 'answers'} (listas de 4 itens, A-D)
def generate_exercise(topic):
    try:
        raw = _chat(
            EXERCISE_SYSTEM_PROMPT, EXERCISE_USER_TEMPLATE.format(topic=topic),
            temperature=1,  # Aumenta a variação das perguntas geradas
            frequency_penalty=0,
            presence_penalty=0
        )
    except Exception as e:
        raw = f"Erro ao processar o prompt: {str(e)}"
    return parse_exercise(raw)


def parse_exercise(raw):
    # Inicializa os valores padrão
    question = "Pergunta não encontrada"
    alternatives = ["Alternativa não encontrada"] * 4
    answers = ["Resposta não encontrada"] * 4

    # Separa a string usando '$' como delimitador
    if '$' in raw:
        question, alternative_answer = raw.split('$', 1)  # Divide no primeiro $
        question = question.strip()

        # Separa alternativas e respostas usando '#'
        alternative_blocks = alternative_answer.split('#')

        if len(alternative_blocks) >= 4:
            for i in range(4):
                if '|' in alternative_blocks[i]:
                    alternative, correctness = alternative_blocks[i].split('|', 1)
                    alternatives[i] = alternative.strip()
                    answers[i] = correctness.strip()

    return {'question': question, 'alternatives': alternatives, 'answers': answers}
