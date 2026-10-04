import { montarChat } from "./chat.js";
import { api, barraDeFiltros, cabecalho, dias, el, guardarNaUrl, mensagem, nomeDaCategoria, numero } from "./comum.js";

cabecalho("comprador");
montarChat();

const POR_PAGINA = 50;
const SITUACOES = [
  ["em_ruptura", "Só em ruptura"],
  ["sem_venda", "Sem venda"],
  ["com_transito", "Com compra a caminho"],
];
const ORDENS = [
  ["cobertura", "Dias que segura"],
  ["venda_diaria", "Venda por dia"],
  ["nome", "Nome"],
];

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("estoque");
const barra = document.querySelector(".barra-estoque");
const total = document.getElementById("total");
const ordem = document.getElementById("ordem");
const filtros = barraDeFiltros(document.getElementById("filtros"), () => {
  pagina = 1;
  carregar();
});

const daUrl = new URLSearchParams(location.search);
let pagina = Math.max(1, Number.parseInt(daUrl.get("pagina"), 10) || 1);

ordem.append(...ORDENS.map(([valor, rotulo]) => el("option", { value: valor }, rotulo)));
ordem.value = ORDENS.some(([valor]) => valor === daUrl.get("ordem")) ? daUrl.get("ordem") : "cobertura";
ordem.addEventListener("change", () => {
  pagina = 1;
  carregar();
});

function linkDoSku(codigo) {
  return `sku.html?sku=${encodeURIComponent(codigo)}`;
}

function vendaPorDia(valor) {
  if (valor === 0) return el("span", { class: "suave" }, "sem venda");
  if (valor < 0.1) return "menos de 0,1";
  return numero(valor, 1);
}

function segura(item) {
  if (item.cobertura_dias === null) return el("span", { class: "suave" }, "sem venda");
  return [
    item.disponivel === 0 ? "Zerado" : dias(item.cobertura_dias),
    item.em_ruptura ? el("span", { class: "selo urgente" }, "Ruptura") : null,
  ];
}

function linha(item) {
  return el(
    "tr",
    { class: item.em_ruptura ? "em-ruptura" : null },
    el(
      "td",
      { class: "produto" },
      el("a", { href: linkDoSku(item.sku_code) }, el("strong", {}, item.produto_nome)),
      el("span", {}, `${item.cor} · ${item.tamanho} `, el("code", {}, item.sku_code)),
    ),
    el("td", { "data-rotulo": "Categoria", class: "categoria" }, nomeDaCategoria(item.categoria)),
    el("td", { "data-rotulo": "Estoque", class: "num" }, numero(item.disponivel)),
    el("td", { "data-rotulo": "A caminho", class: "num" }, item.em_transito ? numero(item.em_transito) : el("span", { class: "suave" }, "-")),
    el("td", { "data-rotulo": "Venda/dia", class: "num" }, vendaPorDia(item.venda_media_diaria)),
    el("td", { "data-rotulo": "Segura", class: "num segura" }, segura(item)),
  );
}

function tabela(itens) {
  return el(
    "div",
    { class: "tabela tabela-estoque" },
    el(
      "table",
      {},
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          el("th", {}, "Produto"),
          el("th", {}, "Categoria"),
          el("th", { class: "num" }, "Em estoque"),
          el("th", { class: "num" }, "A caminho"),
          el("th", { class: "num" }, "Venda por dia"),
          el("th", { class: "num" }, "Segura"),
        ),
      ),
      el("tbody", {}, itens.map(linha)),
    ),
  );
}

function irParaPagina(nova) {
  pagina = nova;
  carregar().then(() => barra.scrollIntoView({ block: "start", behavior: "smooth" }));
}

function paginacao(resultado) {
  const paginas = Math.max(1, Math.ceil(resultado.total / resultado.por_pagina));
  if (paginas === 1) return null;
  return el(
    "nav",
    { class: "paginacao", "aria-label": "Páginas" },
    el("button", { type: "button", disabled: pagina <= 1, onclick: () => irParaPagina(pagina - 1) }, "← Anterior"),
    el("span", {}, `Página ${numero(Math.min(pagina, paginas))} de ${numero(paginas)}`),
    el("button", { type: "button", disabled: pagina >= paginas, onclick: () => irParaPagina(pagina + 1) }, "Próxima →"),
  );
}

function nenhumComFiltros() {
  return el(
    "div",
    { class: "card vazio" },
    el("strong", {}, "Nenhum SKU com esses filtros"),
    el("p", { class: "suave" }, "Tente outra palavra ou veja o estoque inteiro."),
    el("button", { type: "button", onclick: filtros.limpar }, "Limpar filtros"),
  );
}

function foraDasPaginas(resultado) {
  return el(
    "div",
    { class: "card vazio" },
    el("strong", {}, "Esta página não existe mais"),
    el("p", { class: "suave" }, `São ${numero(resultado.total)} SKUs com esses filtros.`),
    el("button", { type: "button", onclick: () => irParaPagina(1) }, "Ir para a primeira página"),
  );
}

function textoDoTotal(resultado) {
  if (resultado.total === 0) return "";
  const inicio = (resultado.pagina - 1) * resultado.por_pagina + 1;
  const fim = inicio + resultado.itens.length - 1;
  const quantos = resultado.total === 1 ? "1 SKU" : `${numero(resultado.total)} SKUs`;
  if (resultado.itens.length === 0 || resultado.total <= resultado.por_pagina) return quantos;
  return `${numero(inicio)} a ${numero(fim)} de ${quantos}`;
}

function mostrar(resultado) {
  total.textContent = textoDoTotal(resultado);
  barra.hidden = false;
  if (resultado.total === 0) {
    conteudo.replaceChildren(nenhumComFiltros());
    return;
  }
  if (resultado.itens.length === 0) {
    conteudo.replaceChildren(foraDasPaginas(resultado));
    return;
  }
  conteudo.replaceChildren(tabela(resultado.itens), paginacao(resultado));
}

let ultimaConsulta = 0;

async function carregar() {
  const parametros = { ...filtros.valores() };
  if (ordem.value !== "cobertura") parametros.ordem = ordem.value;
  if (pagina > 1) parametros.pagina = pagina;
  guardarNaUrl(parametros);
  const consulta = new URLSearchParams({ ...parametros, por_pagina: POR_PAGINA }).toString();
  const esta = ++ultimaConsulta;
  conteudo.setAttribute("aria-busy", "true");
  try {
    const resultado = await api("GET", `/estoque?${consulta}`);
    if (esta === ultimaConsulta) mostrar(resultado);
  } catch (e) {
    if (esta !== ultimaConsulta) return;
    conteudo.replaceChildren(mensagem("erro", e.status === 503 ? e.message : `Não foi possível ler o estoque: ${e.message}`));
  } finally {
    if (esta === ultimaConsulta) conteudo.removeAttribute("aria-busy");
  }
}

try {
  const categorias = await api("GET", "/categorias");
  filtros.opcoes("categoria", categorias.map((c) => [c, nomeDaCategoria(c)]));
  filtros.opcoes("situacao", SITUACOES);
  filtros.mostrar();
  await carregar();
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", e.status === 503 ? e.message : `Não foi possível ler o estoque: ${e.message}`));
} finally {
  carregando.remove();
}
