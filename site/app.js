// ===================================================================
// PreçoCerto - front-end do comparador (JavaScript puro, sem framework)
// ===================================================================

const form = document.querySelector("#form-busca");
const campo = document.querySelector("#campo-busca");
const botao = form.querySelector("button");
const secaoResultados = document.querySelector("#resultados");
const listaResultados = document.querySelector("#lista-resultados");
const listaAcompanhando = document.querySelector("#lista-acompanhando");
const statusEl = document.querySelector("#status");
const modal = document.querySelector("#modal-historico");

const seletorLojas = document.querySelector("#seletor-lojas");
const avisoLojas = document.querySelector("#aviso-lojas");
const contadorLojas = document.querySelector("#contador-lojas");

const LOJAS_PERMITIDAS = [
  "amazon.com.br", "kabum.com.br", "mercadolivre.com.br",
  "pichau.com.br", "terabyteshop.com.br", "magazineluiza.com.br",
];
const CHAVE_STORAGE = "precocerto:lojas";

// ----------------------------------------------------------- utilidades
const formatador = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const moeda = (v) => formatador.format(v);

// Os nomes vêm de sites de terceiros: nunca coloque no HTML sem escapar
function escapar(texto) {
  const mapa = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(texto ?? "").replace(/[&<>"']/g, (c) => mapa[c]);
}

// Só aceita links das lojas que comparamos
function linkSeguro(url) {
  try {
    const u = new URL(url);
    const ok = u.protocol === "https:" && LOJAS_PERMITIDAS.some((d) => u.hostname.endsWith(d));
    return ok ? u.href : "#";
  } catch {
    return "#";
  }
}

// "Mercado Livre" -> "mercadolivre" (usado nas classes CSS)
const classeLoja = (nome) =>
  nome.normalize("NFD").replace(/[^a-zA-Z]/g, "").toLowerCase();

// Cor da loja vem do CSS (variáveis --amazon, --kabum...)
const corDaLoja = (nome) =>
  getComputedStyle(document.documentElement).getPropertyValue(`--${classeLoja(nome)}`).trim() || "#555";

async function pegarJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    throw new Error(corpo.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

// --------------------------------------------------------------- cards
function criarCard(produto) {
  const temEconomia = produto.economia > 0.009;
  const selo = temEconomia
    ? `<span class="selo">Economize ${moeda(produto.economia)}</span>`
    : `<span class="selo selo--igual">Mesmo preço</span>`;
  const similar = produto.similaridade ? `<span class="similar">${produto.similaridade}% de correspondência</span>` : "";

  const ofertas = produto.ofertas.map((o, i) => {
    const melhor = i === 0 && temEconomia;
    const minimo = o.minimo30d && o.minimo30d < o.preco
      ? `<small>mín. 30 dias: ${moeda(o.minimo30d)}</small>` : "";
    return `
      <li class="oferta ${melhor ? "oferta--melhor" : ""}">
        <span class="loja loja--${classeLoja(o.loja)}">${escapar(o.loja)}${minimo}</span>
        <span class="preco">${moeda(o.preco)}</span>
        <a class="btn btn--comprar" href="${linkSeguro(o.url)}" target="_blank" rel="noopener noreferrer">
          Comprar
        </a>
      </li>`;
  }).join("");

  const historico = produto.id
    ? `<button class="btn btn--secundario" data-historico="${produto.id}" data-nome="${escapar(produto.nome)}">Ver histórico</button>`
    : "";

  return `
    <article class="card">
      <div class="card__topo">${selo}${similar}</div>
      <h3 class="card__titulo" title="${escapar(produto.nome)}">${escapar(produto.nome)}</h3>
      <ul class="ofertas">${ofertas}</ul>
      <div class="card__rodape">
        <span class="minimo">Melhor preço: <strong>${escapar(produto.melhorLoja)}</strong></span>
        ${historico}
      </div>
    </article>`;
}

function mostrarCarregando(alvo, qtd = 3) {
  alvo.innerHTML = '<div class="esqueleto"></div>'.repeat(qtd);
}

function mostrarVazio(alvo, mensagem) {
  alvo.innerHTML = `<div class="vazio">${mensagem}</div>`;
}

// ------------------------------------------------------ seletor de lojas
function lojasMarcadas() {
  return [...seletorLojas.querySelectorAll("input:checked")].map((i) => i.value);
}

function atualizarSelecao() {
  const marcadas = lojasMarcadas();
  const total = seletorLojas.querySelectorAll("input").length;
  contadorLojas.textContent = `(${marcadas.length} de ${total})`;
  avisoLojas.hidden = marcadas.length >= 2;
  try { localStorage.setItem(CHAVE_STORAGE, JSON.stringify(marcadas)); } catch {}
}

async function carregarLojas() {
  let salvas = null;
  try { salvas = JSON.parse(localStorage.getItem(CHAVE_STORAGE)); } catch {}
  try {
    const lojas = await pegarJson("/api/lojas");
    seletorLojas.innerHTML = lojas.map((l) => `
      <label class="opcao-loja opcao-loja--${classeLoja(l.nome)}">
        <input type="checkbox" value="${escapar(l.id)}" ${!salvas || salvas.includes(l.id) ? "checked" : ""}>
        <span>${escapar(l.nome)}</span>
      </label>`).join("");
    atualizarSelecao();
  } catch {
    seletorLojas.innerHTML = '<p class="lojas__aviso">Não foi possível carregar as lojas.</p>';
  }
}

seletorLojas.addEventListener("change", atualizarSelecao);

// --------------------------------------------------------------- busca
async function buscar(termo) {
  const lojas = lojasMarcadas();
  if (lojas.length < 2) {
    avisoLojas.hidden = false;
    seletorLojas.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  secaoResultados.hidden = false;
  botao.disabled = true;
  botao.textContent = "Buscando…";
  statusEl.textContent = `Procurando "${termo}" em ${lojas.length} lojas…`;
  mostrarCarregando(listaResultados);
  secaoResultados.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const dados = await pegarJson(
      `/api/buscar?q=${encodeURIComponent(termo)}&lojas=${lojas.join(",")}`);
    const porLoja = Object.entries(dados.encontrados)
      .map(([loja, qtd]) => `${loja}: ${qtd}`).join(" · ");
    statusEl.textContent =
      `${dados.resultados.length} produto(s) em 2 lojas ou mais — encontrados por loja: ${porLoja}`;

    if (!dados.resultados.length) {
      mostrarVazio(listaResultados,
        "Não achamos o mesmo produto em duas lojas ou mais. Tente um termo mais específico, com marca e modelo.");
    } else {
      listaResultados.innerHTML = dados.resultados.map(criarCard).join("");
    }
    carregarAcompanhando();
  } catch (erro) {
    statusEl.textContent = "";
    mostrarVazio(listaResultados, `Não foi possível buscar agora (${escapar(erro.message)}). Tente novamente.`);
  } finally {
    botao.disabled = false;
    botao.textContent = "Comparar";
  }
}

// A janela do topo mostra o último produto real pesquisado (se houver)
function mostrarNaVitrine(produto) {
  const vitrine = document.querySelector("#vitrine");
  if (!vitrine || !produto) return;
  vitrine.innerHTML = criarCard(produto);
  const janela = vitrine.closest(".janela");
  janela.removeAttribute("aria-hidden");
  janela.querySelector(".janela__url").textContent = "precocerto · última busca";
}

async function carregarAcompanhando() {
  try {
    const produtos = await pegarJson("/api/produtos");
    if (!produtos.length) {
      mostrarVazio(listaAcompanhando, "Nenhum produto salvo ainda. Faça uma busca para começar.");
      return;
    }
    listaAcompanhando.innerHTML = produtos.map(criarCard).join("");
    mostrarNaVitrine(produtos[0]);
  } catch {
    mostrarVazio(listaAcompanhando, "Histórico indisponível (verifique a conexão com o banco).");
  }
}

// -------------------------------------------------------------- gráfico
function desenharGrafico(pontos) {
  const L = 600, A = 260, m = { t: 16, r: 16, b: 32, l: 72 };
  const tempos = pontos.map((p) => new Date(p.data).getTime());
  const precos = pontos.map((p) => p.preco);
  const tMin = Math.min(...tempos), tMax = Math.max(...tempos);
  const folga = (Math.max(...precos) - Math.min(...precos)) * 0.15 || Math.max(...precos) * 0.05;
  const pMin = Math.min(...precos) - folga, pMax = Math.max(...precos) + folga;

  const x = (t) => m.l + (tMax === tMin ? 0.5 : (t - tMin) / (tMax - tMin)) * (L - m.l - m.r);
  const y = (p) => m.t + (1 - (p - pMin) / (pMax - pMin)) * (A - m.t - m.b);

  let svg = "";
  for (let i = 0; i <= 3; i++) {
    const v = pMin + ((pMax - pMin) * i) / 3;
    svg += `<line class="grade-linha" x1="${m.l}" x2="${L - m.r}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text class="eixo" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${moeda(v)}</text>`;
  }
  const data = (t) => new Date(t).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  svg += `<text class="eixo" x="${m.l}" y="${A - 8}">${data(tMin)}</text>`;
  svg += `<text class="eixo" x="${L - m.r}" y="${A - 8}" text-anchor="end">${data(tMax)}</text>`;

  const porLoja = Object.groupBy
    ? Object.groupBy(pontos, (p) => p.loja)
    : pontos.reduce((g, p) => ((g[p.loja] ??= []).push(p), g), {});

  for (const [loja, lista] of Object.entries(porLoja)) {
    const cor = corDaLoja(loja);
    const coords = lista.map((p) => `${x(new Date(p.data).getTime())},${y(p.preco)}`);
    svg += `<polyline points="${coords.join(" ")}" fill="none" stroke="${cor}" stroke-width="2.5" stroke-linejoin="round"/>`;
    lista.forEach((p) => {
      svg += `<circle cx="${x(new Date(p.data).getTime())}" cy="${y(p.preco)}" r="4" fill="#fff" stroke="${cor}" stroke-width="2">
                <title>${loja}: ${moeda(p.preco)} em ${new Date(p.data).toLocaleString("pt-BR")}</title></circle>`;
    });
  }

  const legenda = Object.keys(porLoja)
    .map((l) => `<span style="color:${corDaLoja(l)}">● ${escapar(l)}</span>`).join("");
  return `<svg viewBox="0 0 ${L} ${A}" role="img" aria-label="Gráfico do histórico de preços">${svg}</svg>
          <div class="legenda">${legenda}</div>`;
}

async function abrirHistorico(id, nome) {
  document.querySelector("#modal-titulo").textContent = nome;
  const grafico = document.querySelector("#grafico");
  grafico.innerHTML = '<div class="esqueleto" style="height:200px"></div>';
  modal.showModal();
  try {
    const pontos = await pegarJson(`/api/produtos/${id}/historico`);
    grafico.innerHTML = pontos.length
      ? desenharGrafico(pontos)
      : '<div class="vazio">Sem histórico ainda.</div>';
  } catch {
    grafico.innerHTML = '<div class="vazio">Não foi possível carregar o histórico.</div>';
  }
}

// --------------------------------------------------------------- eventos
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const termo = campo.value.trim();
  if (termo.length >= 2) buscar(termo);
});

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    campo.value = chip.textContent;
    buscar(chip.textContent);
  })
);

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-historico]");
  if (btn) abrirHistorico(btn.dataset.historico, btn.dataset.nome);
  if (e.target.closest("[data-fechar]") || e.target === modal) modal.close();
});

carregarLojas();
carregarAcompanhando();
