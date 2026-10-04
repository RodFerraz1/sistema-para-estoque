import { montarChat } from "./chat.js";
import {
  MOTIVOS,
  TIPOS_DE_AVISO,
  api,
  barraDeFiltros,
  cabecalho,
  coberturaEmDias,
  dataHora,
  dias,
  el,
  guardarNaUrl,
  mensagem,
  nomeDaCategoria,
  numero,
  quando,
  resumoDaDecisao,
  selosDeMotivo,
} from "./comum.js";

cabecalho("comprador");
montarChat();

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("painel");
const filtros = barraDeFiltros(document.getElementById("filtros"), carregar);

const GRUPOS = [
  {
    id: "pedidos_de_vendas",
    titulo: "Pedidos da equipe de vendas",
    descricao: () => "Avisos que as vendedoras mandaram e ainda não têm decisão.",
    cor: "var(--vendas)",
  },
  {
    id: "em_ruptura",
    titulo: "Em ruptura",
    descricao: (piso) =>
      `O estoque segura menos de ${dias(piso)} de venda, o mínimo da sua política. Os zerados vêm primeiro, depois o que acaba antes.`,
    cor: "var(--urgente)",
    motivo: "abaixo_do_piso_alerta",
  },
  {
    id: "vao_faltar",
    titulo: "Vão faltar antes da compra chegar",
    descricao: () => "Pelo prazo do fornecedor, mesmo comprando hoje o estoque acaba antes da mercadoria chegar.",
    cor: "var(--urgente)",
    motivo: "ruptura_antes_da_chegada",
  },
  {
    id: "outros_alertas",
    titulo: "Outros alertas",
    descricao: () => "Outros motivos de alerta que você escolheu na política de compra.",
    cor: "var(--destaque)",
  },
];

document.getElementById("saudacao").textContent = saudacao();

function saudacao() {
  const hora = new Date().getHours();
  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

function linkDoSku(codigo) {
  return `sku.html?sku=${encodeURIComponent(codigo)}`;
}

function frase(item, grupo, piso) {
  if (grupo === "vao_faltar") {
    const naChegada = item.cobertura_na_chegada_sem_compra_dias;
    if (naChegada < 0) return `Acaba cerca de ${dias(-naChegada)} antes de uma compra feita hoje chegar.`;
    return `Quando uma compra feita hoje chegar, ainda sobram ${dias(naChegada)} de estoque.`;
  }
  if (item.disponivel === 0 && item.cobertura_atual_dias !== null) return "Zerado: já está faltando na loja.";
  if (item.motivos.includes("abaixo_do_piso_alerta")) return `Abaixo dos ${dias(piso)} de venda que o estoque precisa segurar.`;
  return null;
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

const MOTIVO_DO_GRUPO = { em_ruptura: "abaixo_do_piso_alerta", vao_faltar: "ruptura_antes_da_chegada" };

function motivosAlemDoGrupo(item, grupo) {
  return item.motivos.filter((m) => m !== MOTIVO_DO_GRUPO[grupo]);
}

function cartao(item, { id, cor }, piso) {
  const motivos = motivosAlemDoGrupo(item, id);
  const zerado = item.disponivel === 0;
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
      frase(item, id, piso) ? el("div", { class: "frase" }, frase(item, id, piso)) : null,
      el(
        "div",
        { class: "item-numeros" },
        el("span", {}, "Em estoque ", el("b", {}, `${numero(item.disponivel)} un.`)),
        item.cobertura_atual_dias === null
          ? el("span", {}, "Sem vendas recentes")
          : el("span", {}, "Segura ", el("b", {}, coberturaEmDias(item.cobertura_atual_dias))),
      ),
      zerado || motivos.length
        ? el("div", { class: "selos" }, zerado ? el("span", { class: "selo urgente" }, "Zerado") : null, selosDeMotivo(motivos))
        : null,
    ),
    sugestao(item),
  );
}

function grupo({ id, titulo, descricao, cor }, itens, piso) {
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
      el("p", { class: "suave" }, descricao(piso)),
    ),
    el("div", { class: "itens" }, itens.map((item) => cartao(item, doGrupo, piso))),
  );
}

function resumo(grupos, contagens, decididos) {
  return el(
    "div",
    { class: "resumo" },
    grupos.map((g) =>
      el(
        "a",
        { href: `#${g.id}`, style: `--cor: ${contagens[g.id] ? g.cor : "var(--borda-forte)"}` },
        el("strong", {}, String(contagens[g.id])),
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

function nenhumComFiltros() {
  return el(
    "div",
    { class: "card vazio" },
    el("strong", {}, "Nenhum SKU com esses filtros"),
    el("p", { class: "suave" }, "Nada pedindo atenção com essa busca. Tente outra palavra ou veja o painel inteiro."),
    el("button", { type: "button", onclick: filtros.limpar }, "Limpar filtros"),
  );
}

function mostrar(painel, politica) {
  const { motivos_de_alerta: motivos, piso_alerta_dias: piso } = politica.parametros;
  const grupos = GRUPOS.filter((g) => !g.motivo || motivos.includes(g.motivo));
  const porGrupo = Object.fromEntries(GRUPOS.map((g) => [g.id, []]));
  for (const item of painel.alertas) porGrupo[item.grupo].push(item);
  porGrupo.pedidos_de_vendas.sort((a, b) => b.ultimo_aviso.criado_em.localeCompare(a.ultimo_aviso.criado_em));
  const comFiltro = Object.keys(filtros.valores()).length > 0;
  const vazio = comFiltro ? nenhumComFiltros() : tudoEmDia();
  conteudo.replaceChildren(
    el(
      "div",
      {},
      skusComErro(painel.skus_com_erro),
      resumo(grupos, painel.contagens, painel.decididos),
      painel.alertas.length ? grupos.map((g) => grupo(g, porGrupo[g.id], piso)) : vazio,
      decididos(painel.decididos),
    ),
  );
}

function montarFiltros(politica, categorias, fornecedores) {
  const ruptura = "abaixo_do_piso_alerta";
  const motivos = [...politica.parametros.motivos_de_alerta].sort((a, b) => (b === ruptura) - (a === ruptura));
  filtros.opcoes("categoria", categorias.map((c) => [c, nomeDaCategoria(c)]));
  filtros.opcoes("motivo", [["aviso", "Aviso da equipe de vendas"], ...motivos.map((m) => [m, MOTIVOS[m] ?? m])]);
  filtros.opcoes("fornecedor", fornecedores.map((f) => [f.id, f.nome]));
  filtros.mostrar();
}

let politica;
let ultimaConsulta = 0;

async function carregar() {
  const consulta = guardarNaUrl(filtros.valores());
  const numero = ++ultimaConsulta;
  conteudo.setAttribute("aria-busy", "true");
  try {
    const painel = await api("GET", `/painel?${consulta}`);
    if (numero === ultimaConsulta) mostrar(painel, politica);
  } catch (e) {
    if (numero !== ultimaConsulta) return;
    conteudo.replaceChildren(mensagem("erro", e.status === 503 ? e.message : `Não foi possível calcular o painel: ${e.message}`));
  } finally {
    if (numero === ultimaConsulta) conteudo.removeAttribute("aria-busy");
  }
}

try {
  const [politicaAtiva, categorias, fornecedores] = await Promise.all([
    api("GET", "/politica-compra"),
    api("GET", "/categorias"),
    api("GET", "/fornecedores"),
  ]);
  politica = politicaAtiva;
  montarFiltros(politica, categorias, fornecedores);
  await carregar();
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", e.status === 503 ? e.message : `Não foi possível calcular o painel: ${e.message}`));
} finally {
  carregando.remove();
}
