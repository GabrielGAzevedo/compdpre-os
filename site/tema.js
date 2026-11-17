// Tema claro/escuro. Carregado no <head> para aplicar o tema antes de
// desenhar a página (sem "piscar" branco). Sem escolha salva, segue o sistema.
(function () {
  var CHAVE = "precocerto:tema";
  var raiz = document.documentElement;
  var midia = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function lerSalvo() {
    try { return localStorage.getItem(CHAVE); } catch (e) { return null; }
  }
  function atual() {
    return raiz.getAttribute("data-theme") || (midia && midia.matches ? "dark" : "light");
  }

  var salvo = lerSalvo();
  if (salvo === "dark" || salvo === "light") raiz.setAttribute("data-theme", salvo);

  function atualizarBotao() {
    var escuro = atual() === "dark";
    var botao = document.querySelector("[data-tema]");
    if (botao) {
      botao.setAttribute("aria-label", escuro ? "Usar tema claro" : "Usar tema escuro");
      botao.setAttribute("title", escuro ? "Tema claro" : "Tema escuro");
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", escuro ? "#0f1412" : "#f5f4ef");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var botao = document.querySelector("[data-tema]");
    if (!botao) return;
    atualizarBotao();
    botao.addEventListener("click", function () {
      var novo = atual() === "dark" ? "light" : "dark";
      raiz.setAttribute("data-theme", novo);
      try { localStorage.setItem(CHAVE, novo); } catch (e) {}
      atualizarBotao();
    });
    if (midia && midia.addEventListener) midia.addEventListener("change", atualizarBotao);
  });
})();
