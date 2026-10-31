from django.shortcuts import render

from .services import llm

MIN_FLASHCARDS = 1
MAX_FLASHCARDS = 5
DEFAULT_FLASHCARDS = 3


def _render_page(request, template, generate, **context):
    """Renderiza a tela; num POST, chama `generate` com o texto do usuário e exibe o resultado ou o erro."""
    context.setdefault('prompt', '')
    status = 200

    if request.method == 'POST':
        user_prompt = request.POST.get('user_prompt', '').strip()
        context['prompt'] = user_prompt
        if user_prompt:
            try:
                context['result'] = generate(user_prompt)
            except llm.LLMError as e:
                context['error'] = e.message
                status = e.status
        else:
            context['error'] = "Por favor, forneça um prompt."
            status = 400

    return render(request, template, context, status=status)


# View da tela de resumo (assistente de engenharia)
def index(request):
    return _render_page(request, "index.html", llm.explain_concept)


def _flashcard_quantity(request):
    try:
        quantity = int(request.POST.get('quantity', DEFAULT_FLASHCARDS))
    except ValueError:
        return DEFAULT_FLASHCARDS
    return max(MIN_FLASHCARDS, min(quantity, MAX_FLASHCARDS))


# View da tela de flashcards
def flashcards(request):
    quantity = _flashcard_quantity(request)
    return _render_page(
        request, "flashcards.html",
        lambda topic: llm.generate_flashcards(topic, quantity),
        quantity=quantity,
        quantity_options=range(MIN_FLASHCARDS, MAX_FLASHCARDS + 1)
    )


# View da tela de exercícios (múltipla escolha)
def exercicios(request):
    return _render_page(request, "exercicios.html", llm.generate_exercise)
