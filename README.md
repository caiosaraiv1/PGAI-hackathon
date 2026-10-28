# PGAI — Assistente de estudos para engenharia com OpenAI

Aplicação web em Django que usa a OpenAI API (`gpt-3.5-turbo`) para ajudar estudantes de engenharia: explica conceitos, gera flashcards e cria questões de múltipla escolha a partir de um tema digitado pelo usuário. Projeto desenvolvido em equipe durante um hackathon.

<!--
  Captura de tela: substitua o caminho abaixo pela imagem da aplicação e descomente.
  ![Tela do PGAI](docs/screenshot.png)
-->

## Funcionalidades implementadas

| Tela | Rota | O que faz |
|---|---|---|
| **Resumo** (assistente) | `/` | O usuário escreve uma pergunta e o modelo responde como assistente de engenharia (definições, fórmulas, exemplos, passo a passo). A resposta é convertida para HTML: quebras de linha, negrito em rótulos como "Definição:" e "Exemplo:", listas e blocos de código. |
| **Flashcards** | `/flashcards` | A partir de um tema, gera **um** flashcard por envio, com a pergunta na "frente" e a resposta no "verso". |
| **Exercícios** | `/exercicios` | A partir de um tema, gera **uma** questão de múltipla escolha com 4 alternativas (A–D). Passar o mouse sobre uma alternativa mostra se ela está correta ou incorreta. |

Cada envio é uma chamada independente ao modelo: não há histórico de conversa, contas de usuário nem dados persistidos.

## Stack

- **Python 3.12** (versões fixadas no `requirements.txt` não instalam em Python 3.14)
- **Django 5.1** — views e templates HTML/CSS (sem framework de front-end)
- **OpenAI Python SDK 1.x** — Chat Completions API, modelo `gpt-3.5-turbo`
- **python-dotenv** — carrega a `OPENAI_API_KEY` de um arquivo `.env`
- SQLite (padrão do Django; a aplicação não define modelos próprios)

## Como funciona a integração com o LLM

Toda a lógica de IA fica em `djangotutorial/PGAI/services/`; as views só recebem o formulário, chamam o serviço e renderizam o template.

```
views.py ──► services/llm.py ──► OpenAI Chat Completions (gpt-3.5-turbo)
                 │
                 └── services/prompts.py  (system prompts de cada funcionalidade)
```

- **`services/prompts.py`** — um system prompt por funcionalidade, como constantes nomeadas e comentadas (`CONCEPT_SYSTEM_PROMPT`, `FLASHCARD_SYSTEM_PROMPT`, `EXERCISE_SYSTEM_PROMPT`, `EXERCISE_USER_TEMPLATE`).
- **`services/llm.py`** — cria o cliente OpenAI, faz as chamadas (`explain_concept`, `generate_flashcard`, `generate_exercise`) e converte o texto do modelo em dados para os templates.

**Saída estruturada via contrato no prompt.** Flashcards e exercícios precisam de partes separadas (frente/verso, alternativas, gabarito). Como o projeto usa texto livre, e não JSON mode ou function calling, os prompts definem um formato com delimitadores e o backend faz o parsing:

| Funcionalidade | Formato pedido no prompt | Parser | Parâmetros |
|---|---|---|---|
| Assistente | Texto livre com rótulos ("Definição:", "Exemplo:"…) | `format_response` → HTML | padrão |
| Flashcards | `pergunta \| resposta` | `parse_flashcard` (divide no primeiro `\|`) | `temperature=0.7` |
| Exercícios | `Pergunta $ A) … \| correta # B) … \| incorreta # …` | `parse_exercise` (divide em `$` e `#`, depois em `\|`) | `temperature=1`, para variar as questões |

Se o modelo não respeitar o formato, o parser usa valores padrão ("Resposta não encontrada", "Alternativa não encontrada") em vez de quebrar a página. Erros da API são capturados e a mensagem aparece na própria tela.

**Limitações conhecidas** (comportamento atual, mantido como foi entregue no hackathon):
- Não há limite de tokens (`max_tokens`), cache nem controle de custo.
- O parsing depende de o modelo seguir os delimitadores; não há validação nem nova tentativa.
- A resposta do assistente é renderizada com `|safe` no template, então o HTML gerado a partir da saída do modelo não é escapado.
- O cliente OpenAI é criado na importação do módulo, então o servidor não sobe sem `OPENAI_API_KEY` definida.

## Como rodar

Pré-requisitos: Python 3.12 e uma chave da OpenAI API.

```bash
# 1. Na raiz do repositório, crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure a chave da OpenAI
cp .env.example .env              # Windows: copy .env.example .env
# edite o .env e preencha OPENAI_API_KEY

# 4. Entre na pasta do projeto Django, crie o banco local e suba o servidor
cd djangotutorial
python manage.py migrate
python manage.py runserver
```

Acesse http://127.0.0.1:8000/ e use o menu para alternar entre Resumo, Flashcards e Exercícios.

## Estrutura de pastas

```
PGAI-hackathon/
├── .env.example            # variáveis de ambiente necessárias (sem valores)
├── requirements.txt
└── djangotutorial/         # projeto Django (rode o manage.py daqui)
    ├── manage.py
    └── PGAI/
        ├── settings.py
        ├── urls.py         # rotas: /, /flashcards, /exercicios
        ├── views.py        # recebem o formulário, chamam services.llm e renderizam
        ├── services/
        │   ├── llm.py      # cliente OpenAI, chamadas ao modelo e parsing das respostas
        │   └── prompts.py  # system prompts de cada funcionalidade
        └── templates/
            ├── index.html       # assistente ("Resumo")
            ├── flashcards.html
            └── exercicios.html
```

## Autoria

Projeto desenvolvido em equipe durante o hackathon. Fui responsável pelo **backend** (Django), pela **integração com a OpenAI API** e pela **engenharia de prompts**: os system prompts e os formatos de saída que o backend interpreta.

<!-- Adicione aqui seu nome, LinkedIn e os créditos dos demais integrantes da equipe. -->

## Desafio do hackathon

Texto original do enunciado:

> Criar uma ferramenta de IA que ajude estudantes universitários e profissionais a otimizar tempo e produtividade nos estudos.
>
> O objetivo e utilizar modelos de IA através de API para criar planos de estudo para um determinado tema, resumir textos, explicar conceitos e gerar quizzes para fixação do aprendizado. A solução deve se integrar com uma ou mais fontes acadêmicas (axXiv, SciHub, Google Scholar) ou outras fontes de informações técnicas (StackOverflow? Wikipédia).
>
> A interface de usuário pode ser um utilitário de linha de comando (CLI), Web ou aplicativo móvel (Android, iOS ou ambos).
>
> Diferencial: Implementação eficiente com limite de uso de tokens/processamento para otimizar recursos computacionais.
