# PGAI — Assistente de estudos para engenharia com Gemini

Aplicação web em Django que usa a Gemini API (`gemini-3.8-flash` por padrão) para ajudar estudantes de engenharia: explica conceitos, gera flashcards e cria questões de múltipla escolha a partir de um tema digitado pelo usuário. Projeto desenvolvido em equipe durante um hackathon.

<!--
  Captura de tela: substitua o caminho abaixo pela imagem da aplicação e descomente.
  ![Tela do PGAI](docs/screenshot.png)
-->

## Funcionalidades implementadas

| Tela | Rota | O que faz |
|---|---|---|
| **Resumo** (assistente) | `/` | O usuário escreve uma pergunta e o modelo responde como assistente de engenharia, em seções com parágrafos, listas de passos e, quando ajudam, fórmulas ou diagramas em texto puro. |
| **Flashcards** | `/flashcards/` | A partir de um tema, gera de **1 a 5** flashcards por envio. O card vira ao clicar, com navegação entre os cards. |
| **Exercícios** | `/exercicios/` | A partir de um tema, gera **uma** questão de múltipla escolha com 4 alternativas (A–D). Ao clicar em uma alternativa, o app marca certa ou errada e mostra a explicação. |

A interface é responsiva e mostra um indicador enquanto espera o modelo, além de avisos específicos para limite de requisições (429), indisponibilidade (503) e resposta inválida. Cada envio é uma chamada independente ao modelo: não há histórico de conversa, contas de usuário nem dados persistidos.

## Stack

- **Python 3.12** (versões fixadas no `requirements.txt` não instalam em Python 3.14)
- **Django 5.1** — views e templates, com CSS e JavaScript puros (sem framework de front-end nem etapa de build)
- **OpenAI Python SDK 1.x** — apontado para o endpoint do Gemini compatível com a OpenAI (Chat Completions API), modelo configurável por `LLM_MODEL`
- **Pydantic 2** — define os schemas das respostas e as valida
- **python-dotenv** — carrega as variáveis de ambiente de um arquivo `.env`
- SQLite (padrão do Django; a aplicação não define modelos próprios)

## Como funciona a integração com o LLM

Toda a lógica de IA fica em `djangotutorial/PGAI/services/`; as views só recebem o formulário, chamam o serviço e renderizam o template.

```
views.py ──► services/llm.py ──► Gemini (endpoint compatível com a OpenAI)
                 │
                 ├── services/prompts.py   (system prompts de cada funcionalidade)
                 ├── services/schemas.py   (formato e validação das respostas)
                 └── services/fixtures/    (respostas usadas no modo mock)
```

- **`services/prompts.py`** — um system prompt por funcionalidade, como constantes nomeadas, com as regras de escrita em comum (português acentuado, sem LaTeX nem Markdown, fórmulas em texto puro).
- **`services/schemas.py`** — modelos Pydantic `Exercicio`, `Flashcards` e `Resumo`. Eles geram o JSON Schema enviado à API e validam o que volta.
- **`services/llm.py`** — cria o cliente do SDK `openai` com a `base_url` do Gemini e `max_retries=1`, faz as chamadas (`explain_concept`, `generate_flashcards`, `generate_exercise`) e converte falhas em erros com mensagem para a tela.

**Saída estruturada com JSON.** Cada chamada envia `response_format` com `json_schema`, e o resultado é sempre validado com Pydantic. Se o JSON vier inválido ou incompleto, a tela mostra uma mensagem de erro clara.

| Funcionalidade | Schema | Campos | Parâmetros |
|---|---|---|---|
| Resumo | `Resumo` | `titulo`, `secoes[1–6]` com `titulo`, `paragrafos`, `itens` e `bloco` | padrão |
| Flashcards | `Flashcards` | `cards[1–5]` com `frente` e `verso` | `temperature=0.7` |
| Exercícios | `Exercicio` | `pergunta`, `alternativas[4]` com `letra` e `texto`, `correta`, `explicacao` | `temperature=1`, para variar as questões |

**Fallback.** Se o endpoint rejeitar o `json_schema` com erro 400, o app pede o JSON no próprio prompt, sem `response_format`, e aplica a mesma validação. Esse envio gasta uma requisição a mais; depois disso, o schema rejeitado segue direto pelo fallback até o servidor reiniciar.

**Retentativas.** Com `max_retries=1`, o SDK repete uma vez, sozinho, as respostas 429 e 5xx. Um envio com falha pode gastar 2 requisições da cota.

**Limitações conhecidas:**
- Não há limite de tokens (`max_tokens`), cache nem controle de custo.
- O gabarito do exercício vai no HTML da página, então pode ser visto no código-fonte.
- A validação garante o formato da resposta, não que o conteúdo técnico esteja correto.

## Como rodar

Pré-requisitos: Python 3.12 e uma chave da Gemini API (veja [Como gerar a chave](#como-gerar-a-chave-do-gemini)). No [modo mock](#modo-mock), a chave é dispensada.

```bash
# 1. Na raiz do repositório, crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure a chave do Gemini
cp .env.example .env              # Windows: copy .env.example .env
# edite o .env e preencha GEMINI_API_KEY

# 4. Entre na pasta do projeto Django, crie o banco local e suba o servidor
cd djangotutorial
python manage.py migrate
python manage.py runserver
```

Acesse http://127.0.0.1:8000/ e use o menu para alternar entre Resumo, Flashcards e Exercícios.

### Como gerar a chave do Gemini

1. Acesse o [Google AI Studio](https://aistudio.google.com/apikey) e entre com sua conta Google.
2. Clique em **Create API key** e escolha ou crie um projeto.
3. Copie a chave para o `.env`, na raiz do repositório. O `.env` é ignorado pelo git; nunca coloque a chave em arquivos versionados.

```dotenv
GEMINI_API_KEY=sua_chave_aqui
LLM_MODEL=
LLM_MOCK=
```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | Sim, exceto no modo mock | Chave gerada no Google AI Studio. |
| `LLM_MODEL` | Não | Nome do modelo. Se ficar vazia, usa `gemini-3.8-flash`. |
| `LLM_MOCK` | Não | Use `1` para ativar o [modo mock](#modo-mock). |

No free tier, cada envio de formulário gasta ao menos uma requisição. Em outubro de 2026, a API retornou limites de 5 requisições por minuto e 20 por dia. Os limites valem por projeto, variam por modelo e a cota diária renova à meia-noite do horário do Pacífico; os valores atuais aparecem no [AI Studio](https://ai.dev/rate-limit). O Google pode usar o conteúdo enviado no free tier para melhorar seus produtos, então não envie dados sensíveis.

## Modo mock

Com `LLM_MOCK=1`, o app usa as respostas de `services/fixtures/` em vez da API: não gasta cota, não precisa de chave e passa pela mesma validação de uma resposta real.

```bash
cd djangotutorial
LLM_MOCK=1 python manage.py runserver
```

No PowerShell, rode `$env:LLM_MOCK=1` antes do `runserver`. Também é possível definir `LLM_MOCK=1` no `.env`.

Para ver os estados de erro, digite um destes textos no campo de qualquer tela:

| Texto | Simula |
|---|---|
| `mock:429` | Limite de requisições atingido |
| `mock:503` | Serviço indisponível |
| `mock:invalido` | Resposta inválida ou incompleta do modelo |

## Testes

Os testes usam apenas mocks e nunca chamam a API.

```bash
cd djangotutorial
python manage.py test PGAI
```

## Estrutura de pastas

```
PGAI-hackathon/
├── .env.example            # variáveis de ambiente necessárias (sem valores)
├── requirements.txt
└── djangotutorial/         # projeto Django (rode o manage.py daqui)
    ├── manage.py
    └── PGAI/
        ├── settings.py
        ├── urls.py         # rotas: /, /flashcards/, /exercicios/
        ├── views.py        # recebem o formulário, chamam services.llm e renderizam
        ├── services/
        │   ├── llm.py      # cliente do Gemini, chamadas ao modelo, mock e erros
        │   ├── prompts.py  # system prompts de cada funcionalidade
        │   ├── schemas.py  # schemas Pydantic das respostas
        │   └── fixtures/   # respostas válidas e inválidas do modo mock
        ├── static/
        │   ├── css/app.css
        │   └── js/app.js   # carregamento, flashcards e exercícios
        ├── templates/
        │   ├── base.html        # cabeçalho, navegação, formulário e alertas
        │   ├── index.html       # assistente ("Resumo")
        │   ├── flashcards.html
        │   └── exercicios.html
        └── tests/          # testes de serviços e views, somente com mocks
```

## Autoria

Projeto desenvolvido em equipe durante o hackathon. Fui responsávelpela **integração com a OpenAI API** e pela **engenharia de prompts**: os system prompts e os formatos de saída que o backend interpreta.

## Desafio do hackathon

Texto original do enunciado:

> Criar uma ferramenta de IA que ajude estudantes universitários e profissionais a otimizar tempo e produtividade nos estudos.
>
> O objetivo e utilizar modelos de IA através de API para criar planos de estudo para um determinado tema, resumir textos, explicar conceitos e gerar quizzes para fixação do aprendizado. A solução deve se integrar com uma ou mais fontes acadêmicas (axXiv, SciHub, Google Scholar) ou outras fontes de informações técnicas (StackOverflow? Wikipédia).
>
> A interface de usuário pode ser um utilitário de linha de comando (CLI), Web ou aplicativo móvel (Android, iOS ou ambos).
>
> Diferencial: Implementação eficiente com limite de uso de tokens/processamento para otimizar recursos computacionais.
