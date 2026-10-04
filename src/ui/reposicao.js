import { api, barraDeFiltros, cabecalho, dataCurta, el, guardarNaUrl, mensagem, nomeDaCategoria, numero } from "./comum.js";

cabecalho("reposicao");

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("painel");
const filtros = barraDeFiltros(document.getElementById("filtros"), carregar);

const DIAS_DA_SEMANA = ["no domingo", "na segunda", "na terça", "na quarta", "na quinta", "na sexta", "no sábado"];
const UMA_SEMANA_MS = 7 * 24 * 60 * 60 * 1000;

function quandoFoi(isoDia) {
  const [ano, mes, dia] = isoDia.split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  return Date.now() - data < UMA_SEMANA_MS ? DIAS_DA_SEMANA[data.getDay()] : `em ${dataCurta(isoDia)}`;
}

function porDia(valor) {
  const arredondado = Math.round(valor * 10) / 10;
  return numero(arredondado, Number.isInteger(arredondado) ? 0 : 1);
}

function emSequencia(partes) {
  return partes.length > 1 ? `${partes.slice(0, -1).join(", ")} e ${partes.at(-1)}` : partes[0];
}

function frase(item) {
  const dias = item.ultimos_dias.map((d) => `${numero(d.quantidade)} ${quandoFoi(d.dia)}`);
  return `Vendia ${porDia(item.venda_diaria_base)} por dia. Vendeu ${emSequencia(dias)}.`;
}

const RESULTADOS = [
  { resultado: "repus", texto: "Repus", classe: "primario repus" },
  { resultado: "estava_na_gondola", texto: "Estava na gôndola" },
  { resultado: "sem_estoque_no_deposito", texto: "Não tem no depósito" },
];

function recadoDoResultado(item, resultado) {
  const nome = `${item.produto_nome} ${item.cor}`;
  if (resultado === "sem_estoque_no_deposito") {
    return `${nome}: a compradora vai saber que o ERP diz ${numero(item.disponivel)} un. e o depósito não tem.`;
  }
  const feito = resultado === "repus" ? "reposto" : "estava na gôndola";
  return `${nome}: ${feito}. Sai da lista e só volta se passar mais um dia inteiro sem vender.`;
}

function verificacao(item) {
  const id = `comentario-${item.sku_code}`;
  const comentario = el("input", { id, type: "text", maxlength: "2000", placeholder: "Ex.: estava no lugar errado" });
  const erro = el("div", {});
  const botoes = RESULTADOS.map(({ resultado, texto, classe }) => {
    const botao = el("button", { type: "button", class: classe ?? "" }, texto);
    botao.addEventListener("click", async () => {
      botoes.forEach((b) => (b.disabled = true));
      try {
        await api("POST", `/skus/${encodeURIComponent(item.sku_code)}/verificacoes`, {
          resultado,
          comentario: comentario.value.trim() || null,
        });
        recadoDaVerificacao = recadoDoResultado(item, resultado);
        await carregar();
      } catch (e) {
        erro.replaceChildren(mensagem("erro", `Não foi registrado: ${e.message}`));
        botoes.forEach((b) => (b.disabled = false));
      }
    });
    return botao;
  });
  return el(
    "div",
    { class: "verificar" },
    el("label", { for: id }, "O que você achou? ", el("span", { class: "suave" }, "Comentário opcional")),
    comentario,
    el("div", { class: "resultados-verificacao" }, botoes),
    erro,
  );
}

function cartao(item) {
  const perdidas = Math.round(item.venda_perdida);
  return el(
    "article",
    { class: "card repor" },
    el(
      "div",
      { class: "repor-topo" },
      el(
        "div",
        { class: "item-produto" },
        el("strong", {}, item.produto_nome),
        el("span", {}, `${item.cor} · ${item.tamanho}`),
        el("code", {}, item.sku_code),
      ),
      el("span", { class: "selo urgente" }, `~${numero(perdidas)} ${perdidas === 1 ? "venda perdida" : "vendas perdidas"}`),
    ),
    el("p", { class: "frase" }, frase(item)),
    el(
      "dl",
      { class: "numeros grandes" },
      el("div", {}, el("dt", {}, "Vendia por dia"), el("dd", {}, porDia(item.venda_diaria_base))),
      el("div", {}, el("dt", {}, `Vendeu em ${item.ultimos_dias.length} dias`), el("dd", {}, numero(item.vendido_na_janela))),
      el("div", {}, el("dt", {}, "No estoque (ERP)"), el("dd", {}, `${numero(item.disponivel)} un.`)),
    ),
    verificacao(item),
  );
}

function vazio() {
  if (Object.keys(filtros.valores()).length) {
    return el(
      "div",
      { class: "card vazio" },
      el("strong", {}, "Nenhum produto com esses filtros"),
      el("p", { class: "suave" }, "Tente outra palavra ou outra categoria."),
      el("button", { type: "button", onclick: filtros.limpar }, "Limpar filtros"),
    );
  }
  return el(
    "div",
    { class: "card vazio" },
    el("strong", {}, "Nada parado na gôndola"),
    el("p", { class: "suave" }, "Nenhum produto com estoque parou de vender nos últimos dias em que a loja abriu."),
  );
}

function mostrar(painel) {
  const itens = painel.quedas_de_venda;
  const recado = recadoDaVerificacao;
  recadoDaVerificacao = null;
  conteudo.replaceChildren(
    el(
      "div",
      {},
      recado ? mensagem("sucesso", recado) : null,
      el(
        "section",
        { class: "grupo", "aria-labelledby": "t-quedas" },
        el(
          "header",
          {},
          el("h2", { id: "t-quedas" }, "Pararam de vender e têm estoque"),
          el("span", { class: "contagem" }, String(itens.length)),
          el("p", { class: "suave" }, "Vendiam todo dia e quase não venderam desde então. Veja se estão na gôndola e diga o que achou. Quem perde mais venda vem primeiro."),
        ),
        itens.length ? el("div", { class: "itens" }, itens.map(cartao)) : vazio(),
      ),
    ),
  );
}

let ultimaConsulta = 0;
let recadoDaVerificacao = null;

async function carregar() {
  const consulta = guardarNaUrl(filtros.valores());
  const numeroDaConsulta = ++ultimaConsulta;
  conteudo.setAttribute("aria-busy", "true");
  try {
    const painel = await api("GET", `/reposicao/painel?${consulta}`);
    if (numeroDaConsulta === ultimaConsulta) mostrar(painel);
  } catch (e) {
    if (numeroDaConsulta === ultimaConsulta) conteudo.replaceChildren(mensagem("erro", `Não foi possível montar o painel: ${e.message}`));
  } finally {
    if (numeroDaConsulta === ultimaConsulta) conteudo.removeAttribute("aria-busy");
  }
}

try {
  const categorias = await api("GET", "/categorias");
  filtros.opcoes("categoria", categorias.map((c) => [c, nomeDaCategoria(c)]));
  filtros.mostrar();
  await carregar();
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", `Não foi possível montar o painel: ${e.message}`));
} finally {
  carregando.remove();
}
