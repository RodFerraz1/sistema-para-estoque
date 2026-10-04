import { montarChat } from "./chat.js";
import {
  MOTIVOS,
  TIPOS_DE_AVISO,
  api,
  barraDeFiltros,
  cabecalho,
  coberturaEmDias,
  dataCurta,
  dataHora,
  dias,
  el,
  guardarNaUrl,
  hojeIso,
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
    id: "entregas_atrasadas",
    titulo: "Entregas atrasadas",
    descricao: () =>
      "Já comprou e não chegou: pedidos com a data prevista vencida, por fornecedor, para você ligar uma vez e cobrar tudo. Primeiro quem tem produto em ruptura.",
    cor: "var(--destaque)",
    motivo: "entrega_atrasada",
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

const MOTIVO_DO_GRUPO = {
  entregas_atrasadas: "entrega_atrasada",
  em_ruptura: "abaixo_do_piso_alerta",
  vao_faltar: "ruptura_antes_da_chegada",
};

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

function plural(n, singular, varios) {
  return `${numero(n)} ${n === 1 ? singular : varios}`;
}

function textoDoHistorico(h) {
  if (h.entregas_recebidas === 0) return "ainda não tem entrega recebida com data prevista no ERP.";
  if (h.entregas_atrasadas === 0) return `entregou no prazo ${plural(h.entregas_recebidas, "entrega recebida", "entregas recebidas")}.`;
  return `atrasou ${numero(h.entregas_atrasadas)} de ${plural(h.entregas_recebidas, "entrega recebida", "entregas recebidas")}, em média ${dias(h.media_dias_de_atraso)}.`;
}

function historicoDeAtrasos(fornecedorId) {
  const linha = el("p", { class: "suave historico-atrasos" }, "Carregando o histórico de entregas...");
  api("GET", `/fornecedores/${fornecedorId}/atrasos`)
    .then((h) => linha.replaceChildren("Histórico: ", textoDoHistorico(h)))
    .catch(() => linha.remove());
  return linha;
}

function textoDaCobranca(c) {
  const quem = `${c.cobrado_por} cobrou em ${dataHora(c.criado_em)}`;
  if (c.nova_previsao) return `${quem}: a nova previsão de ${dataCurta(c.nova_previsao)} passou e a mercadoria não chegou.`;
  return `${quem}, sem nova previsão, e a mercadoria não chegou em 7 dias.`;
}

function skuAtrasado(s) {
  return el(
    "li",
    {},
    el(
      "div",
      { class: "item-produto" },
      el("a", { href: linkDoSku(s.sku_code) }, el("strong", {}, `${s.produto_nome}, ${s.cor}, ${s.tamanho}`)),
      el("code", {}, s.sku_code),
    ),
    el(
      "div",
      { class: "item-numeros" },
      el("span", {}, "Faltam chegar ", el("b", {}, `${numero(s.quantidade_pendente)} un.`)),
      el("span", {}, "Em estoque ", el("b", {}, `${numero(s.disponivel)} un.`)),
      s.cobertura_dias === null
        ? el("span", {}, "Sem vendas recentes")
        : el("span", {}, "Segura ", el("b", {}, coberturaEmDias(s.cobertura_dias))),
    ),
    el(
      "div",
      { class: "selos" },
      s.disponivel === 0 ? el("span", { class: "selo urgente" }, "Zerado") : null,
      s.em_ruptura && s.disponivel > 0 ? el("span", { class: "selo urgente" }, "Em ruptura") : null,
    ),
  );
}

function formularioDeCobranca(pedido, fornecedor) {
  const id = pedido.pedido_id;
  const previsao = el("input", { id: `previsao-${id}`, type: "date", min: hojeIso() });
  const comentario = el("input", { id: `comentario-${id}`, type: "text", maxlength: "2000", placeholder: "Ex.: caminhão parado na estrada" });
  const botao = el("button", { type: "submit", class: "primario" }, "Registrar cobrança");
  const resultado = el("div", {});
  const formulario = el(
    "form",
    { class: "form-cobranca", novalidate: true },
    el("div", { class: "campo" }, el("label", { for: `previsao-${id}` }, "Nova previsão ", el("span", { class: "suave" }, "(opcional)")), previsao),
    el("div", { class: "campo" }, el("label", { for: `comentario-${id}` }, "O que o fornecedor disse ", el("span", { class: "suave" }, "(opcional)")), comentario),
    botao,
    resultado,
  );
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    botao.disabled = true;
    try {
      const cobranca = await api("POST", `/pedidos/${id}/cobrancas`, {
        nova_previsao: previsao.value || null,
        comentario: comentario.value.trim() || null,
      });
      const ate = cobranca.nova_previsao ? `depois de ${dataCurta(cobranca.nova_previsao)}` : "em 7 dias";
      recadoDaCobranca = `Cobrança da ${fornecedor} registrada. O pedido sai do painel e volta ${ate} se a mercadoria não chegar.`;
      await carregar();
    } catch (e) {
      resultado.replaceChildren(mensagem("erro", `A cobrança não foi registrada: ${e.message}`));
      botao.disabled = false;
    }
  });
  return el(
    "details",
    { class: "cobrar" },
    el("summary", { class: "botao" }, "Cobrei o fornecedor"),
    formulario,
  );
}

function pedidoAtrasado(pedido, fornecedor) {
  return el(
    "div",
    { class: "pedido-atrasado" },
    el(
      "div",
      { class: "pedido-cabecalho" },
      el("span", {}, "Pedido ", el("code", {}, pedido.pedido_id.slice(0, 8).toUpperCase()), ` · previsto para ${dataCurta(pedido.data_prevista_entrega)}`),
      el("span", { class: "selo destaque" }, `${plural(pedido.dias_de_atraso, "dia", "dias")} de atraso`),
    ),
    pedido.ultima_cobranca ? el("p", { class: "recado-cobranca" }, textoDaCobranca(pedido.ultima_cobranca)) : null,
    el("ul", { class: "skus-atrasados" }, pedido.skus.map(skuAtrasado)),
    formularioDeCobranca(pedido, fornecedor),
  );
}

function fornecedorAtrasado(f) {
  return el(
    "article",
    { class: "fornecedor-atrasado", style: `--cor: ${f.tem_sku_em_ruptura ? "var(--urgente)" : "var(--destaque)"}` },
    el(
      "header",
      {},
      el("h3", {}, f.fornecedor_nome),
      f.tem_sku_em_ruptura ? el("span", { class: "selo urgente" }, "Tem produto em ruptura") : null,
    ),
    historicoDeAtrasos(f.fornecedor_id),
    f.pedidos.map((p) => pedidoAtrasado(p, f.fornecedor_nome)),
  );
}

function cabecalhoDoGrupo({ id, titulo, descricao }, contagem, piso) {
  return el(
    "header",
    {},
    el("h2", { id: `t-${id}` }, titulo),
    el("span", { class: "contagem" }, String(contagem)),
    el("p", { class: "suave" }, descricao(piso)),
  );
}

function grupoDeEntregas(g, itens, fornecedores) {
  if (fornecedores.length === 0) return null;
  return el(
    "section",
    { class: "grupo", id: g.id, "aria-labelledby": `t-${g.id}` },
    cabecalhoDoGrupo(g, itens.length),
    el("div", { class: "itens" }, fornecedores.map(fornecedorAtrasado)),
  );
}

function grupo(g, itens, piso) {
  const doGrupo = { id: g.id, cor: g.cor };
  if (itens.length === 0) return null;
  return el(
    "section",
    { class: "grupo", id: g.id, "aria-labelledby": `t-${g.id}` },
    cabecalhoDoGrupo(g, itens.length, piso),
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
  const recado = recadoDaCobranca;
  recadoDaCobranca = null;
  conteudo.replaceChildren(
    el(
      "div",
      {},
      recado ? mensagem("sucesso", recado) : null,
      skusComErro(painel.skus_com_erro),
      resumo(grupos, painel.contagens, painel.decididos),
      painel.alertas.length
        ? grupos.map((g) =>
            g.id === "entregas_atrasadas"
              ? grupoDeEntregas(g, porGrupo[g.id], painel.entregas_atrasadas)
              : grupo(g, porGrupo[g.id], piso),
          )
        : vazio,
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
let recadoDaCobranca = null;

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
