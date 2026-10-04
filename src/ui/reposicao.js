import { api, barraDeFiltros, cabecalho, dataCurta, el, guardarNaUrl, mensagem, nomeDaCategoria, numero, quando } from "./comum.js";

cabecalho("reposicao");

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("painel");
const filtros = barraDeFiltros(document.getElementById("filtros"), carregar);

const DIAS_DA_SEMANA = ["no domingo", "na segunda", "na terça", "na quarta", "na quinta", "na sexta", "no sábado"];
const UMA_SEMANA_MS = 7 * 24 * 60 * 60 * 1000;

let setores = [];

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

function frase(queda) {
  const dias = queda.ultimos_dias.map((d) => `${numero(d.quantidade)} ${quandoFoi(d.dia)}`);
  return `Vendia ${porDia(queda.venda_diaria_base)} por dia. Vendeu ${emSequencia(dias)}.`;
}

const RESULTADOS = [
  { resultado: "repus", texto: "Repus", classe: "primario repus" },
  { resultado: "estava_na_gondola", texto: "Estava na gôndola" },
  { resultado: "sem_estoque_no_deposito", texto: "Não tem no depósito" },
];

function recadoDoResultado(item, resultado, comAviso) {
  const nome = `${item.produto_nome} ${item.cor}`;
  const vendedora = comAviso ? " A vendedora que avisou vai saber." : "";
  if (resultado === "sem_estoque_no_deposito") {
    return `${nome}: a compradora vai saber que o ERP diz ${numero(item.disponivel)} un. e o depósito não tem.${vendedora}`;
  }
  const feito = resultado === "repus" ? "reposto" : "estava na gôndola";
  return `${nome}: ${feito}. Sai da lista e só volta se passar mais um dia inteiro sem vender.${vendedora}`;
}

function escolhaDoSetor(item) {
  const id = `setor-${item.sku_code}`;
  const atual = item.setor;
  const select = el(
    "select",
    { id },
    el("option", { value: "" }, atual ? `Fica em ${atual.nome}` : "Setor não informado"),
    setores.filter((s) => s.id !== atual?.id).map((s) => el("option", { value: s.id }, `Mudar para ${s.nome}`)),
  );
  return { select, campo: el("div", { class: "campo-setor" }, el("label", { for: id }, "Setor"), select) };
}

function verificacao(item, comAviso) {
  const id = `comentario-${item.sku_code}`;
  const comentario = el("input", { id, type: "text", maxlength: "2000", placeholder: "Ex.: estava no lugar errado" });
  const setor = escolhaDoSetor(item);
  const erro = el("div", {});
  const botoes = RESULTADOS.map(({ resultado, texto, classe }) => {
    const botao = el("button", { type: "button", class: classe ?? "" }, texto);
    botao.addEventListener("click", async () => {
      botoes.forEach((b) => (b.disabled = true));
      try {
        await api("POST", `/skus/${encodeURIComponent(item.sku_code)}/verificacoes`, {
          resultado,
          comentario: comentario.value.trim() || null,
          setor_id: setor.select.value || null,
        });
        recadoDaVerificacao = recadoDoResultado(item, resultado, comAviso);
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
    el(
      "div",
      { class: "verificar-campos" },
      el("div", {}, el("label", { for: id }, "O que você achou? ", el("span", { class: "suave" }, "Comentário opcional")), comentario),
      setor.campo,
    ),
    el("div", { class: "resultados-verificacao" }, botoes),
    erro,
  );
}

function produto(item) {
  return el(
    "div",
    { class: "item-produto" },
    el("strong", {}, item.produto_nome),
    el("span", {}, `${item.cor} · ${item.tamanho}`),
    el("code", {}, item.sku_code),
  );
}

function seloDoSetor(item) {
  return el("span", { class: "selo" }, item.setor ? `Setor ${item.setor.nome}` : "Setor não informado");
}

function numerosDaQueda(queda, disponivel) {
  return el(
    "dl",
    { class: "numeros grandes" },
    el("div", {}, el("dt", {}, "Vendia por dia"), el("dd", {}, porDia(queda.venda_diaria_base))),
    el("div", {}, el("dt", {}, `Vendeu em ${queda.ultimos_dias.length} dias`), el("dd", {}, numero(queda.vendido_na_janela))),
    el("div", {}, el("dt", {}, "No estoque (ERP)"), el("dd", {}, `${numero(disponivel)} un.`)),
  );
}

function cartaoDeQueda(item) {
  const perdidas = Math.round(item.venda_perdida);
  return el(
    "article",
    { class: "card repor" },
    el(
      "div",
      { class: "repor-topo" },
      produto(item),
      el(
        "div",
        { class: "selos" },
        el("span", { class: "selo urgente" }, `~${numero(perdidas)} ${perdidas === 1 ? "venda perdida" : "vendas perdidas"}`),
        seloDoSetor(item),
      ),
    ),
    el("p", { class: "frase" }, frase(item)),
    numerosDaQueda(item, item.disponivel),
    verificacao(item, false),
  );
}

function linhaDoAviso(aviso) {
  return el(
    "li",
    {},
    el("strong", {}, aviso.avisado_por),
    el("span", { class: "suave" }, ` avisou ${quando(aviso.criado_em)}`),
    aviso.comentario ? el("span", { class: "comentario-do-aviso" }, `"${aviso.comentario}"`) : null,
  );
}

function cartaoDeAviso(item) {
  return el(
    "article",
    { class: "card repor aviso-gondola" },
    el(
      "div",
      { class: "repor-topo" },
      produto(item),
      el(
        "div",
        { class: "selos" },
        el("span", { class: "selo vendas" }, "Gôndola vazia"),
        item.queda ? el("span", { class: "selo urgente" }, "Também parou de vender") : null,
        seloDoSetor(item),
      ),
    ),
    el("ul", { class: "avisos-da-gondola", "aria-label": "Quem avisou" }, item.avisos.map(linhaDoAviso)),
    item.queda ? el("p", { class: "frase" }, frase(item.queda)) : null,
    item.queda
      ? numerosDaQueda(item.queda, item.disponivel)
      : el(
          "dl",
          { class: "numeros grandes so-estoque" },
          el("div", {}, el("dt", {}, "No estoque (ERP)"), el("dd", {}, `${numero(item.disponivel)} un.`)),
        ),
    item.disponivel === 0 ? el("p", { class: "suave" }, "O ERP diz que não tem. Se não achar no depósito, a compradora já vê o produto em ruptura.") : null,
    verificacao(item, true),
  );
}

function vazio() {
  if (Object.keys(filtros.valores()).length) {
    return el(
      "div",
      { class: "card vazio" },
      el("strong", {}, "Nenhum produto com esses filtros"),
      el("p", { class: "suave" }, "Tente outra palavra, outro setor ou outra categoria."),
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

function grupo(id, titulo, explicacao, itens, cartao, seVazio) {
  return el(
    "section",
    { class: "grupo", "aria-labelledby": id },
    el(
      "header",
      {},
      el("h2", { id }, titulo),
      el("span", { class: "contagem" }, String(itens.length)),
      el("p", { class: "suave" }, explicacao),
    ),
    itens.length ? el("div", { class: "itens" }, itens.map(cartao)) : seVazio,
  );
}

function mostrar(painel) {
  const recado = recadoDaVerificacao;
  recadoDaVerificacao = null;
  const avisos = painel.avisos_de_gondola;
  conteudo.replaceChildren(
    el(
      "div",
      {},
      recado ? mensagem("sucesso", recado) : null,
      grupo(
        "t-avisos",
        "Avisos das vendedoras",
        "Uma vendedora viu a gôndola vazia. Vá ao setor, veja e diga o que achou. O aviso mais antigo vem primeiro.",
        avisos,
        cartaoDeAviso,
        el("p", { class: "suave nenhum-aviso" }, "Nenhuma gôndola vazia avisada agora."),
      ),
      grupo(
        "t-quedas",
        "Pararam de vender e têm estoque",
        "Vendiam todo dia e quase não venderam desde então. Veja se estão na gôndola e diga o que achou. Quem perde mais venda vem primeiro.",
        painel.quedas_de_venda,
        cartaoDeQueda,
        vazio(),
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
  const [categorias, ativos] = await Promise.all([api("GET", "/categorias"), api("GET", "/setores")]);
  setores = ativos;
  filtros.opcoes("setor", setores.map((s) => [s.id, s.nome]));
  filtros.opcoes("categoria", categorias.map((c) => [c, nomeDaCategoria(c)]));
  filtros.mostrar();
  await carregar();
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", `Não foi possível montar o painel: ${e.message}`));
} finally {
  carregando.remove();
}
