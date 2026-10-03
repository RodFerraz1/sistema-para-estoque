import { montarChat } from "./chat.js";
import {
  TIPOS_DE_AVISO,
  api,
  coberturaAtual,
  dataHora,
  el,
  mensagem,
  numero,
  quando,
  resumoDaDecisao,
  selosDeMotivo,
} from "./comum.js";

montarChat();

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("painel");

const GRUPOS = [
  {
    id: "pedidos-de-vendas",
    titulo: "Pedidos da equipe de vendas",
    descricao: "Avisos que as vendedoras mandaram e ainda não têm decisão.",
    cor: "var(--vendas)",
  },
  {
    id: "vao-faltar",
    titulo: "Vão faltar antes da compra chegar",
    descricao: "Mesmo comprando hoje, o estoque acaba antes da mercadoria chegar.",
    cor: "var(--urgente)",
  },
  {
    id: "outros-alertas",
    titulo: "Outros alertas",
    descricao: "Outros motivos de alerta que você escolheu na política de compra.",
    cor: "var(--destaque)",
  },
];

document.getElementById("saudacao").textContent = saudacao();
document.getElementById("copiar-link").addEventListener("click", async (evento) => {
  const link = new URL("aviso.html", location.href).href;
  try {
    await navigator.clipboard.writeText(link);
    evento.currentTarget.textContent = "Link copiado";
  } catch {
    evento.currentTarget.textContent = link;
  }
});

function saudacao() {
  const hora = new Date().getHours();
  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

function linkDoSku(codigo) {
  return `sku.html?sku=${encodeURIComponent(codigo)}`;
}

function grupoDo(item) {
  if (item.avisos_abertos > 0) return "pedidos-de-vendas";
  if (item.motivos.includes("ruptura_antes_da_chegada")) return "vao-faltar";
  return "outros-alertas";
}

function frase(item) {
  const naChegada = item.cobertura_na_chegada_sem_compra_meses;
  if (naChegada === null) return "Sem cálculo de cobertura para este produto.";
  if (naChegada < 0) return `Acaba cerca de ${numero(-naChegada * 30)} dias antes de uma compra feita hoje chegar.`;
  return `Quando uma compra feita hoje chegar, ainda sobra estoque para ${numero(naChegada, 1)} meses.`;
}

function recado(item) {
  const ultimo = item.ultimo_aviso;
  if (ultimo === null) return null;
  const outros = item.avisos_abertos > 1 ? ` (+${item.avisos_abertos - 1} aviso${item.avisos_abertos > 2 ? "s" : ""})` : "";
  return el(
    "div",
    { class: "recado" },
    el("strong", {}, `${TIPOS_DE_AVISO[ultimo.tipo]}`),
    ` · ${ultimo.avisado_por}, ${quando(ultimo.criado_em)}${outros}`,
    ultimo.comentario ? [el("br"), el("q", {}, ultimo.comentario)] : null,
  );
}

function sugestao(item) {
  if (item.quantidade_sugerida === null) {
    return el("div", { class: "item-sugestao" }, el("small", {}, "Sugestão"), el("strong", {}, "Não comprar agora"));
  }
  return el(
    "div",
    { class: "item-sugestao" },
    el("small", {}, "Sugestão de compra"),
    el("strong", {}, `${numero(item.quantidade_sugerida)} un.`),
    el("small", {}, item.fornecedor_sugerido),
  );
}

function motivosAlemDoGrupo(item, grupo) {
  return grupo === "vao-faltar" ? item.motivos.filter((m) => m !== "ruptura_antes_da_chegada") : item.motivos;
}

function cartao(item, { id, cor }) {
  const motivos = motivosAlemDoGrupo(item, id);
  return el(
    "a",
    { class: "item", href: linkDoSku(item.sku_code), style: `--cor: ${cor}` },
    el(
      "div",
      { class: "item-produto" },
      el("strong", {}, item.produto_nome),
      el("span", {}, `${item.cor} · ${item.tamanho}`),
      el("code", {}, item.sku_code),
    ),
    el(
      "div",
      { class: "item-situacao" },
      recado(item),
      el("div", { class: "frase" }, frase(item)),
      el(
        "div",
        { class: "item-numeros" },
        el("span", {}, "Em estoque ", el("b", {}, `${numero(item.disponivel)} un.`)),
        item.cobertura_atual_meses === null
          ? el("span", {}, "Sem vendas recentes")
          : el("span", {}, "O estoque dura ", el("b", {}, coberturaAtual(item.cobertura_atual_meses))),
      ),
      motivos.length ? el("div", { class: "selos" }, selosDeMotivo(motivos)) : null,
    ),
    sugestao(item),
  );
}

function grupo({ id, titulo, descricao, cor }, itens) {
  const doGrupo = { id, cor };
  if (itens.length === 0) return null;
  return el(
    "section",
    { class: "grupo", id, "aria-labelledby": `t-${id}` },
    el(
      "header",
      {},
      el("h2", { id: `t-${id}` }, titulo),
      el("span", { class: "contagem" }, String(itens.length)),
      el("p", { class: "suave" }, descricao),
    ),
    el("div", { class: "itens" }, itens.map((item) => cartao(item, doGrupo))),
  );
}

function resumo(porGrupo, decididos) {
  return el(
    "div",
    { class: "resumo" },
    GRUPOS.map((g) =>
      el(
        "a",
        { href: `#${g.id}`, style: `--cor: ${porGrupo[g.id].length ? g.cor : "var(--borda-forte)"}` },
        el("strong", {}, String(porGrupo[g.id].length)),
        el("span", {}, g.titulo),
      ),
    ),
    el(
      "a",
      { href: "#decididos", style: "--cor: var(--sucesso)" },
      el("strong", {}, String(decididos.length)),
      el("span", {}, "Decididos nos últimos 7 dias"),
    ),
  );
}

function decididos(itens) {
  return el(
    "details",
    { class: "card decididos", id: "decididos" },
    el("summary", {}, el("strong", {}, `Decididos nos últimos 7 dias (${itens.length})`)),
    itens.length
      ? el(
          "ul",
          { class: "historico" },
          itens.map(({ decisao, ...sku }) =>
            el(
              "li",
              {},
              el("a", { href: linkDoSku(sku.sku_code) }, `${sku.produto_nome}, ${sku.cor}, ${sku.tamanho}`),
              el("div", {}, resumoDaDecisao(decisao)),
              el("div", { class: "suave" }, `${decisao.decidido_por}, ${dataHora(decisao.criado_em)}`),
            ),
          ),
        )
      : el("p", { class: "suave" }, "Nenhuma decisão de compra nos últimos 7 dias."),
    el("p", { class: "suave" }, "O produto volta para o painel quando a decisão faz 7 dias ou quando chega um aviso novo."),
  );
}

function skusComErro(codigos) {
  if (codigos.length === 0) return null;
  return mensagem("aviso", `Ficaram de fora ${codigos.length} SKU(s) sem registro de estoque no ERP: ${codigos.join(", ")}.`);
}

function tudoEmDia() {
  return el(
    "div",
    { class: "card vazio" },
    el("strong", {}, "Tudo em dia"),
    el("p", { class: "suave" }, "Nenhum aviso das vendedoras e nenhum produto em alerta pela política de compra."),
  );
}

function mostrar(painel) {
  const porGrupo = Object.fromEntries(GRUPOS.map((g) => [g.id, []]));
  for (const item of painel.alertas) porGrupo[grupoDo(item)].push(item);
  porGrupo["pedidos-de-vendas"].sort((a, b) => b.ultimo_aviso.criado_em.localeCompare(a.ultimo_aviso.criado_em));
  conteudo.replaceChildren(
    el(
      "div",
      {},
      skusComErro(painel.skus_com_erro),
      resumo(porGrupo, painel.decididos),
      painel.alertas.length ? GRUPOS.map((g) => grupo(g, porGrupo[g.id])) : tudoEmDia(),
      decididos(painel.decididos),
    ),
  );
}

try {
  mostrar(await api("GET", "/painel"));
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", e.status === 503 ? e.message : `Não foi possível calcular o painel: ${e.message}`));
} finally {
  carregando.remove();
}
