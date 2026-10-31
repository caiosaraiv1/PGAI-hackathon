(function () {
    "use strict";

    // Após um POST, a entrada do histórico vira GET: o F5 não reenvia o pedido nem gasta cota
    if ("submitted" in document.body.dataset) {
        history.replaceState(null, "", location.href);
    }

    // Formulário: botão desabilitado e indicador enquanto espera a resposta
    function setLoading(composer, loading) {
        composer.querySelector("[data-submit]").disabled = loading;
        composer.querySelector("[data-spinner]").hidden = !loading;
        composer.querySelector("[data-submit-label]").textContent = loading ? "Gerando…" : "Gerar";
        composer.setAttribute("aria-busy", String(loading));
    }

    var composer = document.querySelector("[data-composer]");
    composer.addEventListener("submit", function () {
        setLoading(composer, true);
    });

    // Ao voltar pelo histórico, o navegador pode restaurar a página com o botão desabilitado
    window.addEventListener("pageshow", function () {
        setLoading(composer, false);
    });

    // Flashcards: vira ao clicar e navega entre os cards
    function setFlipped(card, flipped) {
        card.classList.toggle("is-flipped", flipped);
        card.setAttribute("aria-pressed", String(flipped));
        card.querySelector("[data-face='front']").setAttribute("aria-hidden", String(flipped));
        card.querySelector("[data-face='back']").setAttribute("aria-hidden", String(!flipped));
    }

    function setupDeck(deck) {
        var cards = Array.prototype.slice.call(deck.querySelectorAll("[data-card]"));
        var previous = deck.querySelector("[data-previous]");
        var next = deck.querySelector("[data-next]");
        var position = deck.querySelector("[data-position]");
        var current = 0;

        function show(index) {
            setFlipped(cards[current], false);
            cards[current].hidden = true;
            current = index;
            cards[current].hidden = false;
            position.textContent = (current + 1) + " de " + cards.length;
            previous.disabled = current === 0;
            next.disabled = current === cards.length - 1;
        }

        cards.forEach(function (card) {
            card.addEventListener("click", function () {
                setFlipped(card, !card.classList.contains("is-flipped"));
            });
        });

        if (position) {
            previous.addEventListener("click", function () {
                show(current - 1);
            });
            next.addEventListener("click", function () {
                show(current + 1);
            });
            show(0);
        }
    }

    // Exercícios: marca certa/errada no primeiro clique e mostra a explicação
    function setupExercise(exercise) {
        var options = Array.prototype.slice.call(exercise.querySelectorAll("[data-option]"));
        var correct = exercise.dataset.correct;
        var feedback = exercise.querySelector("[data-feedback]");
        var verdict = exercise.querySelector("[data-verdict]");

        options.forEach(function (option) {
            option.addEventListener("click", function () {
                var chosen = option.dataset.option;
                var isCorrect = chosen === correct;

                options.forEach(function (item) {
                    item.disabled = true;
                    if (item.dataset.option === correct) {
                        item.classList.add("is-correct");
                    }
                });
                if (!isCorrect) {
                    option.classList.add("is-wrong");
                }

                verdict.textContent = isCorrect
                    ? "Correto!"
                    : "Incorreto. A resposta certa é a alternativa " + correct + ".";
                verdict.classList.add(isCorrect ? "is-correct" : "is-wrong");
                feedback.hidden = false;
            });
        });
    }

    document.querySelectorAll("[data-deck]").forEach(setupDeck);
    document.querySelectorAll("[data-exercise]").forEach(setupExercise);
})();
