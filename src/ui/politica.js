import { montarChat } from "./chat.js";
import { api, cabecalho, dataHora, el, mensagem } from "./comum.js";

cabecalho("comprador");

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const NUMEROS = ["teto_meses", "extra_sazonal_meses", "piso_alerta_dias", "piso_reposicao_dias", "ciclo_compra_meses", "dias_historico_minimo"];
const OPCOES = ["criterio_fornecedor", "lead_time_base", "sazonalidade_modo"];
const PERGUNTAS = {
  teto_meses: "pergunta 1",
  extra_sazonal_meses: "pergunta 2",
  meses_quentes: "pergunta 2",
  piso_alerta_dias: "pergunta 3",
  piso_reposicao_dias: "pergunta 4",
  ciclo_compra_meses: "pergunta 5",
  criterio_fornecedor: "pergunta 6",
  lead_time_base: "pergunta 7",
  sazonalidade_modo: "pergunta 8",
  dias_historico_minimo: "pergunta 9",
  motivos_de_alerta: "pergunta 10",
};

montarChat();

const formulario = document.getElementById("politica");
const versao = document.getElementById("versao");
const carregamento = document.getElementById("carregamento");
const resultado = document.getElementById("resultado");
const botao = document.getElementById("salvar");

document.getElementById("meses").append(
  ...MESES.map((nome, i) => el("label", {}, el("input", { type: "checkbox", name: "meses_quentes", value: i + 1 }), nome)),
);

function preencher(politica) {
  const p = politica.parametros;
  for (const campo of NUMEROS) formulario.elements[campo].value = p[campo];
  for (const campo of OPCOES) formulario.elements[campo].value = p[campo];
  for (const caixa of formulario.querySelectorAll('input[name="meses_quentes"]')) {
    caixa.checked = p.meses_quentes.includes(Number(caixa.value));
  }
  for (const caixa of formulario.querySelectorAll('input[name="motivos_de_alerta"]')) {
    caixa.checked = p.motivos_de_alerta.includes(caixa.value);
  }
  versao.textContent = `Versão ${politica.versao} · ${dataHora(politica.criada_em)}`;
}

function parametros() {
  const p = {};
  for (const campo of NUMEROS) p[campo] = Number(formulario.elements[campo].value);
  for (const campo of OPCOES) p[campo] = formulario.elements[campo].value;
  p.meses_quentes = [...formulario.querySelectorAll('input[name="meses_quentes"]:checked')].map((c) => Number(c.value));
  p.motivos_de_alerta = [...formulario.querySelectorAll('input[name="motivos_de_alerta"]:checked')].map((c) => c.value);
  return p;
}

function comPerguntas(texto) {
  return texto.replace(/\b[a-z0-9_]+\b/g, (nome) => (nome in PERGUNTAS ? `${nome} (${PERGUNTAS[nome]})` : nome));
}

function erros(erro) {
  return el(
    "div",
    { class: "mensagem erro", role: "alert" },
    el("div", {}, "A política não foi salva:"),
    el(
      "ul",
      { class: "lista" },
      erro.detalhes.map((d) => el("li", {}, d.campo in PERGUNTAS ? `${PERGUNTAS[d.campo]}: ` : "", comPerguntas(d.mensagem))),
    ),
  );
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  botao.disabled = true;
  resultado.replaceChildren();
  try {
    const politica = await api("PUT", "/politica-compra", parametros());
    preencher(politica);
    resultado.replaceChildren(
      mensagem(
        "sucesso",
        `Política salva: versão ${politica.versao}. O painel e as sugestões de pedido já usam a versão nova.`,
      ),
    );
  } catch (e) {
    resultado.replaceChildren(e.status > 0 ? erros(e) : mensagem("erro", e.message));
  } finally {
    botao.disabled = false;
  }
});

try {
  preencher(await api("GET", "/politica-compra"));
  formulario.hidden = false;
} catch (e) {
  versao.textContent = "";
  carregamento.replaceChildren(mensagem("erro", `Não foi possível carregar a política: ${e.message}`));
}
