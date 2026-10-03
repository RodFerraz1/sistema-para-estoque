import { TIPOS_DE_AVISO, api, cabecalho, el, guardarNome, lerNome, mensagem } from "./comum.js";

cabecalho("vendas");

const CHAVE_DO_NOME = "copilot.vendedora";
const ESPERA_DA_BUSCA_MS = 300;

const formulario = document.getElementById("aviso-form");
const busca = document.getElementById("busca");
const buscaStatus = document.getElementById("busca-status");
const resultados = document.getElementById("resultados");
const escolhido = document.getElementById("escolhido");
const botoesTipo = document.querySelectorAll(".tipos button");
const comentario = document.getElementById("comentario");
const nome = document.getElementById("nome");
const enviar = document.getElementById("enviar");
const resultado = document.getElementById("resultado");

let sku = null;
let tipo = null;
let espera = null;
let ultimaBusca = 0;

nome.value = lerNome(CHAVE_DO_NOME);

function descricao(s) {
  return `${s.produto_nome}, ${s.cor}, ${s.tamanho}`;
}

function escolher(s) {
  sku = s;
  resultados.replaceChildren();
  buscaStatus.textContent = "";
  busca.value = "";
  busca.hidden = true;
  escolhido.replaceChildren(
    el("div", {}, el("strong", {}, descricao(s)), el("div", { class: "suave" }, s.sku_code)),
    el("button", { type: "button", onclick: trocar }, "Trocar"),
  );
  escolhido.hidden = false;
}

function trocar() {
  sku = null;
  escolhido.hidden = true;
  busca.hidden = false;
  busca.focus();
}

async function buscar(texto) {
  const numero = ++ultimaBusca;
  buscaStatus.textContent = "Buscando...";
  try {
    const encontrados = await api("GET", `/skus?busca=${encodeURIComponent(texto)}`);
    if (numero !== ultimaBusca) return;
    buscaStatus.textContent = encontrados.length ? "" : "Nenhum produto encontrado. Tente outra palavra.";
    resultados.replaceChildren(
      ...encontrados.map((s) =>
        el(
          "li",
          {},
          el(
            "button",
            { type: "button", onclick: () => escolher(s) },
            el("strong", {}, s.produto_nome),
            el("span", {}, `${s.cor}, ${s.tamanho}`),
            el("span", { class: "suave" }, s.sku_code),
          ),
        ),
      ),
    );
  } catch (e) {
    if (numero === ultimaBusca) buscaStatus.textContent = e.message;
  }
}

busca.addEventListener("input", () => {
  clearTimeout(espera);
  const texto = busca.value.trim();
  if (texto.length < 2) {
    ultimaBusca++;
    resultados.replaceChildren();
    buscaStatus.textContent = "";
    return;
  }
  espera = setTimeout(() => buscar(texto), ESPERA_DA_BUSCA_MS);
});

for (const botao of botoesTipo) {
  botao.addEventListener("click", () => {
    tipo = botao.dataset.tipo;
    for (const outro of botoesTipo) outro.setAttribute("aria-pressed", String(outro === botao));
  });
}

function faltando() {
  if (sku === null) return "Escolha o produto.";
  if (tipo === null) return "Diga se acabou ou se está vendendo muito.";
  if (!nome.value.trim()) return "Informe o seu nome.";
  return null;
}

function limpar() {
  trocar();
  tipo = null;
  for (const botao of botoesTipo) botao.setAttribute("aria-pressed", "false");
  comentario.value = "";
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const erro = faltando();
  if (erro) {
    resultado.replaceChildren(mensagem("erro", erro));
    return;
  }
  enviar.disabled = true;
  try {
    const aviso = await api("POST", "/avisos", {
      sku_code: sku.sku_code,
      tipo,
      avisado_por: nome.value.trim(),
      comentario: comentario.value.trim() || null,
    });
    guardarNome(aviso.avisado_por, CHAVE_DO_NOME);
    resultado.replaceChildren(
      mensagem("sucesso", `Aviso enviado ao comprador: ${descricao(sku)}, ${TIPOS_DE_AVISO[aviso.tipo].toLowerCase()}. Pode mandar o próximo.`),
    );
    limpar();
  } catch (e) {
    resultado.replaceChildren(mensagem("erro", `O aviso não foi enviado: ${e.message}`));
  } finally {
    enviar.disabled = false;
  }
});
