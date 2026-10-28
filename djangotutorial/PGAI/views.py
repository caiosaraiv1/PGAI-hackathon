from django.shortcuts import render

from .services import llm


# View para renderizar a página e exibir a resposta
def index(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('user_prompt', '').strip()
        if user_prompt:
            answer = llm.explain_concept(user_prompt)
        else:
            answer = "Por favor, forneça um prompt."
        return render(request, "index.html", {'answer': answer, 'prompt': user_prompt})

    return render(request, "index.html", {'answer': '', 'prompt': ''})


# View da tela de flashcards
def flashcards(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('user_prompt', '').strip()
        if user_prompt:
            card = llm.generate_flashcard(user_prompt)
            return render(request, "flashcards.html", {
                'question': card['question'],
                'answer': card['answer'],
                'prompt': user_prompt
            })
        else:
            return render(request, "flashcards.html", {
                'error': "Por favor, forneça um prompt.",
                'prompt': ''
            })

    return render(request, "flashcards.html", {
        'question': '',
        'answer': '',
        'prompt': ''
    })


# View da tela de exercícios (múltipla escolha)
def exercicios(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('user_prompt', '').strip()
        if user_prompt:
            exercise = llm.generate_exercise(user_prompt)
            alternatives = exercise['alternatives']
            answers = exercise['answers']

            return render(request, "exercicios.html", {
                'question': exercise['question'],
                'altA': alternatives[0], 'AnwA': answers[0],
                'altB': alternatives[1], 'AnwB': answers[1],
                'altC': alternatives[2], 'AnwC': answers[2],
                'altD': alternatives[3], 'AnwD': answers[3]
            })

    return render(request, "exercicios.html", {'answer': '', 'prompt': ''})
