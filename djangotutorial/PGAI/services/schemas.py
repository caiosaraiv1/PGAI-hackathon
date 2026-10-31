# Formato das respostas do modelo, um schema por funcionalidade.
#
# Os modelos Pydantic validam a resposta recebida e também geram o JSON Schema
# enviado ao Gemini. A API ignora restrições de tamanho de texto, por isso textos
# vazios são rejeitados aqui, e não no schema enviado.

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _not_blank(value):
    value = value.strip()
    if not value:
        raise ValueError("texto vazio")
    return value


# Preserva a indentação de diagramas ASCII; só remove linhas vazias nas pontas.
def _clean_block(value):
    return value.rstrip().lstrip("\n")


Text = Annotated[str, AfterValidator(_not_blank)]
Letter = Literal["A", "B", "C", "D"]


class LLMSchema(BaseModel):
    model_config = ConfigDict(json_schema_extra={"additionalProperties": False})


class Alternativa(LLMSchema):
    letra: Letter
    texto: Text = Field(description="Texto da alternativa, sem a letra.")


class Exercicio(LLMSchema):
    pergunta: Text = Field(description="Enunciado da questão, sem rótulos como 'Pergunta:'.")
    alternativas: list[Alternativa] = Field(min_length=4, max_length=4)
    correta: Letter = Field(description="Letra da alternativa correta.")
    explicacao: Text = Field(description="Explicação curta da resposta correta.")

    @model_validator(mode="after")
    def check_letters(self):
        self.alternativas.sort(key=lambda alternativa: alternativa.letra)
        if [alternativa.letra for alternativa in self.alternativas] != ["A", "B", "C", "D"]:
            raise ValueError("as alternativas devem usar as letras A, B, C e D uma vez cada")
        return self


class Flashcard(LLMSchema):
    frente: Text = Field(description="Pergunta curta e clara, sem rótulos.")
    verso: Text = Field(description="Resposta clara, completa e concisa, sem rótulos.")


class Flashcards(LLMSchema):
    cards: list[Flashcard] = Field(min_length=1, max_length=5)


class Secao(LLMSchema):
    titulo: Text
    paragrafos: list[Text]
    itens: list[Text] = Field(description="Itens de lista ou passos de um cálculo.")
    bloco: Annotated[str, AfterValidator(_clean_block)] = Field(
        description="Fórmula ou diagrama em texto puro; vazio quando não for necessário."
    )

    @model_validator(mode="after")
    def check_content(self):
        if not (self.paragrafos or self.itens or self.bloco):
            raise ValueError("seção sem conteúdo")
        return self


class Resumo(LLMSchema):
    titulo: Text
    secoes: list[Secao] = Field(min_length=1, max_length=6)


def _inline_refs(node, definitions):
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline_refs(definitions[node["$ref"].rsplit("/", 1)[1]], definitions)
        return {key: _inline_refs(value, definitions) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(item, definitions) for item in node]
    return node


# O Pydantic gera $ref para modelos aninhados, ausente da lista de palavras-chave
# aceitas pelo Gemini; por isso o schema é enviado com as referências expandidas.
def json_schema(schema):
    definition = schema.model_json_schema()
    return _inline_refs(definition, definition.get("$defs", {}))


def response_format(schema):
    return {
        "type": "json_schema",
        "json_schema": {"name": schema.__name__, "strict": True, "schema": json_schema(schema)},
    }
