// Confirmação antes de excluir: qualquer <form data-confirmar="mensagem"> pede confirmação.
document.addEventListener("submit", function (evento) {
    const mensagem = evento.target.dataset.confirmar;
    if (mensagem && !window.confirm(mensagem)) {
        evento.preventDefault();
    }
});

// Capa que não carrega: troca a imagem por um quadro "Sem capa".
document.addEventListener("error", function (evento) {
    const img = evento.target;
    if (img.tagName === "IMG" && img.hasAttribute("data-sem-capa")) {
        const quadro = document.createElement("div");
        quadro.className = "sem-capa";
        quadro.textContent = "Sem capa";
        img.replaceWith(quadro);
    }
}, true);
