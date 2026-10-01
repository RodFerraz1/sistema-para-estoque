import { alertas, api, el, mensagem, numero, percentual, reais, sinais } from "./comum.js";

const INTENCOES = {
  situacao_sku: "Situação do SKU",
  sugestao_compra: "Sugestão de compra",
  politica_ou_fornecedor: "Política ou fornecedor",
  fora_de_escopo: "Fora de escopo",
};
const ACOES = {
  respondeu: "Respondeu",
  confirmou_e_respondeu: "Confirmou o entendimento e respondeu",
  pediu_esclarecimento: "Pediu esclarecimento",
  fora_de_escopo: "Fora de escopo",
};
const FAIXAS = { alta: "Alta", media: "Média", baixa: "Baixa" };
const VEREDITOS = {
  confirmada: "Confirmada",
  sem_suporte: "Sem suporte",
  contradita: "Contradita",
  inventada: "Inventada",
  incerta: "Incerta",
};
const CLASSIFICACOES = { aceito: "Aceito", conflitante: "Conflitante", descartado: "Descartado" };
const CITACAO_NAO_CONFIRMADA = /\[[^[\]\n]*? - (?:não confirmada|o trecho diz o contrário|trecho inexistente)[^[\]\n]*\]/;
const MARCACAO = new RegExp(`\\*\\*([^*\\n]+?)\\*\\*|${CITACAO_NAO_CONFIRMADA.source}`, "g");

const formulario = document.getElementById("pergunta-form");
const campoPergunta = document.getElementById("pergunta");
const botao = document.getElementById("perguntar");
const respostas = document.getElementById("respostas");

function textoComMarcas(texto) {
  const partes = [];
  let inicio = 0;
  for (const trecho of texto.matchAll(MARCACAO)) {
    const [inteiro, negrito] = trecho;
    partes.push(
      texto.slice(inicio, trecho.index),
      negrito === undefined ? el("mark", { class: "nao-confirmada" }, inteiro) : el("strong", {}, negrito),
    );
    inicio = trecho.index + inteiro.length;
  }
  partes.push(texto.slice(inicio));
  return el("div", { class: "texto-resposta" }, partes);
}

function secao(titulo, ...conteudo) {
  return [el("h4", {}, titulo), ...conteudo];
}

function tabela(cabecalho, linhas) {
  return el(
    "div",
    { class: "tabela" },
    el(
      "table",
      {},
      el("thead", {}, el("tr", {}, cabecalho.map((c) => el("th", {}, c)))),
      el("tbody", {}, linhas.map((linha) => el("tr", {}, linha.map((c) => el("td", {}, c))))),
    ),
  );
}

function entendimento(r) {
  const { intencao, produto } = r.entendimento;
  const itens = [
    ["Intenção", `${INTENCOES[intencao.escolha] ?? intencao.escolha} (${percentual(intencao.confianca)})`],
    ["Faixa de confiança", FAIXAS[r.faixa] ?? r.faixa],
    ["Ação", ACOES[r.acao] ?? r.acao],
    ["Produto entendido", `${produto.escolha} (${percentual(produto.confianca)})`],
    ["SKUs", r.identificacao?.skus.length ? r.identificacao.skus.join(", ") : "nenhum"],
    ["Redator", r.redator ?? "sem redator (resposta feita em código)"],
  ];
  return el("dl", { class: "numeros" }, itens.map(([dt, dd]) => el("div", {}, el("dt", {}, dt), el("dd", {}, dd))));
}

function fichas(lista) {
  if (lista.length === 0) return null;
  return secao(
    "Fichas dos SKUs",
    tabela(
      ["SKU", "Produto", "Disponível", "Giro mensal", "Cobertura"],
      lista.map((f) => [
        el("code", {}, f.sku_code),
        f.produto_nome,
        `${numero(f.estoque.quantidade_disponivel)} un.`,
        `${numero(f.giro.unidades_por_mes, 1)} un.`,
        f.cobertura.sem_giro ? "sem giro" : `${numero(f.cobertura.meses, 1)} meses`,
      ]),
    ),
  );
}

function sugestoes(lista) {
  return lista.map(({ sugestao, sinais: sinaisDaSugestao }) =>
    el(
      "div",
      { class: "card" },
      el("h3", {}, "Sugestão de pedido ", el("code", {}, sugestao.sku_code)),
      el(
        "p",
        {},
        sugestao.quantidade > 0
          ? `${numero(sugestao.quantidade)} un. de ${sugestao.fornecedor.fornecedor_nome}, ${reais(sugestao.valor_estimado_centavos)}.`
          : `Sem compra (${sugestao.motivo}).`,
        el("span", { class: "suave" }, ` Política v${sugestao.politica_versao}.`),
      ),
      alertas(sugestao.alertas),
      sinais(sinaisDaSugestao),
    ),
  );
}

function citacoes(lista) {
  if (lista.length === 0) return null;
  return secao(
    "Citações",
    tabela(
      ["Trecho", "Afirmação", "Veredito"],
      lista.map((c) => [
        el("code", {}, c.trecho_id),
        c.afirmacao,
        [
          el("span", { class: c.veredito === "confirmada" ? "selo bom" : "selo ruim" }, VEREDITOS[c.veredito] ?? c.veredito),
          c.confianca === null ? "" : el("div", { class: "suave" }, `confiança ${percentual(c.confianca)}`),
        ],
      ]),
    ),
  );
}

function trechos(lista, conflitos) {
  if (lista.length === 0) return null;
  return secao(
    "Trechos usados",
    lista.map((t) =>
      el(
        "details",
        {},
        el("summary", {}, el("code", {}, t.id), ` ${t.titulo} `, el("span", { class: "selo" }, CLASSIFICACOES[t.classificacao] ?? t.classificacao)),
        el("p", { class: "suave" }, `${t.documento}, ${t.tipo}, ${t.data}`),
        el("div", { class: "texto-resposta" }, t.texto),
      ),
    ),
    conflitos.length
      ? secao(
          "Conflitos entre trechos",
          el(
            "ul",
            { class: "lista" },
            conflitos.map((c) =>
              el("li", {}, el("code", {}, c.trecho_a), " e ", el("code", {}, c.trecho_b), ` (probabilidade ${percentual(c.probabilidade)})`),
            ),
          ),
        )
      : null,
  );
}

function resposta(r) {
  const temMarcas = r.resposta.search(CITACAO_NAO_CONFIRMADA) >= 0;
  return [
    textoComMarcas(r.resposta),
    temMarcas ? el("p", { class: "suave" }, "Em vermelho, citações que o Jev não confirmou no trecho citado.") : null,
    secao("Entendimento", entendimento(r)),
    fichas(r.fichas),
    r.sugestoes.length ? secao("Sugestões", sugestoes(r.sugestoes)) : null,
    citacoes(r.citacoes),
    trechos(r.trechos, r.conflitos),
    el("p", { class: "suave" }, "Registro de decisão: ", el("code", {}, r.registro_id)),
  ];
}

async function perguntar(evento) {
  evento.preventDefault();
  const pergunta = campoPergunta.value.trim();
  if (!pergunta) return;
  const corpo = el("div", {}, mensagem("aviso", "O Copilot está consultando os dados e o corpus. Pode levar alguns segundos."));
  respostas.prepend(el("article", { class: "card" }, el("p", { class: "suave" }, "Você perguntou: ", el("strong", {}, pergunta)), corpo));
  botao.disabled = true;
  try {
    corpo.replaceChildren(el("div", {}, resposta(await api("POST", "/chat", { pergunta }))));
    campoPergunta.value = "";
  } catch (e) {
    corpo.replaceChildren(mensagem("erro", e.message));
  } finally {
    botao.disabled = false;
  }
}

formulario.addEventListener("submit", perguntar);
campoPergunta.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && (evento.ctrlKey || evento.metaKey)) formulario.requestSubmit();
});
