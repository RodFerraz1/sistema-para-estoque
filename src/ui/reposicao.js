import { api, cabecalho, el, fraseDaQueda, fraseDaReposicao, mensagem, numero, porDia, quando } from "./comum.js";

cabecalho("reposicao");

const carregando = document.getElementById("carregando");
const conteudo = document.getElementById("painel");
const dialogo = document.getElementById("confirmar-acao");

let setores = [];

const RESULTADOS = [
  { resultado: "repus", texto: "Repus", classe: "primario repus" },
  { resultado: "sem_estoque_no_deposito", texto: "Não tem no depósito" },
];

const RECADOS = {
  repus: "reposto",
  sem_estoque_no_deposito: "não tem no depósito",
};

function recadoDoResultado(item, resultado) {
  return `${item.produto_nome} ${item.cor}: ${RECADOS[resultado]}.`;
}

function confirmar(item, acao) {
  document.getElementById("t-confirmar-acao").textContent = `${item.produto_nome} ${item.cor} · ${item.tamanho}`;
  document.getElementById("acao-a-confirmar").textContent = acao;
  dialogo.showModal();
  return new Promise((resolve) => {
    const fim = new AbortController();
    const responder = (sim) => {
      fim.abort();
      resolve(sim);
    };
    dialogo.addEventListener("submit", (e) => responder(e.submitter?.value === "confirmar"), { signal: fim.signal });
    dialogo.addEventListener("cancel", () => responder(false), { signal: fim.signal });
  });
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

function pecas(n) {
  return `${numero(n)} ${n === 1 ? "peça" : "peças"}`;
}

// Quantas peças a gôndola precisava: as que a vendedora pediu no aviso mais recente que diz
// quantas, se não as que a hora de repor manda levar. Vazio quando ninguém sabe.
function precisava(item) {
  const pedido = [...(item.avisos ?? [])].reverse().find((a) => a.pecas)?.pecas;
  return pedido ?? item.reposicao?.a_repor ?? null;
}

// O depósito não tinha tudo: registra o que foi reposto e pede ao comprador o que faltou.
function reposicaoParcial(item, extras = () => ({})) {
  const id = item.sku_code;
  const total = precisava(item);
  const precisavaDe = el("input", { id: `precisava-${id}`, type: "number", inputmode: "numeric", min: "2", max: "10000", step: "1", value: total ?? "" });
  const pos = el("input", { id: `pos-${id}`, type: "number", inputmode: "numeric", min: "1", max: "10000", step: "1" });
  if (total && item.disponivel > 0 && item.disponivel < total) pos.value = item.disponivel;
  const falta = el("p", { class: "falta", "aria-live": "polite" });
  const enviar = el("button", { type: "submit", class: "primario" }, "Pedir ao comprador o que faltou");
  const erro = el("div", {});

  function faltaram() {
    const de = Number(precisavaDe.value);
    const foram = Number(pos.value);
    return Number.isInteger(de) && Number.isInteger(foram) && foram > 0 && foram < de ? de - foram : null;
  }

  function atualizar() {
    const n = faltaram();
    enviar.disabled = n === null;
    enviar.textContent = n === null ? "Pedir ao comprador o que faltou" : `Pedir ${pecas(n)} ao comprador`;
    falta.replaceChildren(n === null ? "" : el("strong", {}, `Faltaram ${pecas(n)}.`));
  }

  const formulario = el(
    "form",
    { class: "repor-parte", hidden: true, novalidate: true },
    el(
      "div",
      { class: "repor-parte-campos" },
      el("div", { class: "campo" }, el("label", { for: precisavaDe.id }, "A gôndola precisava de"), el("div", { class: "unidade" }, precisavaDe, " peças")),
      el("div", { class: "campo" }, el("label", { for: pos.id }, "Você pôs"), el("div", { class: "unidade" }, pos, " peças")),
    ),
    falta,
    enviar,
    erro,
  );
  formulario.addEventListener("input", atualizar);
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const n = faltaram();
    if (n === null) return;
    if (!(await confirmar(item, `Repus ${pecas(Number(pos.value))} e pedir ${pecas(n)} ao comprador`))) return;
    enviar.disabled = true;
    try {
      await api("POST", `/skus/${encodeURIComponent(item.sku_code)}/falta-na-gondola`, {
        pecas_pedidas: Number(precisavaDe.value),
        pecas_repostas: Number(pos.value),
        ...extras(),
      });
      recadoDaVerificacao = `${item.produto_nome} ${item.cor}: repostas ${pecas(Number(pos.value))}, ${pecas(n)} pedidas ao comprador.`;
      await carregar();
    } catch (e) {
      erro.replaceChildren(mensagem("erro", `Não foi registrado: ${e.message}`));
      enviar.disabled = false;
    }
  });
  atualizar();

  const abrir = el("button", { type: "button", class: "repus-parte", "aria-expanded": "false" }, "Repus só uma parte");
  abrir.addEventListener("click", () => {
    formulario.hidden = !formulario.hidden;
    abrir.setAttribute("aria-expanded", String(!formulario.hidden));
    if (!formulario.hidden) (precisavaDe.value ? pos : precisavaDe).focus();
  });
  return { abrir, formulario };
}

function verificacao(item) {
  const id = `comentario-${item.sku_code}`;
  const comentario = el("input", { id, type: "text", maxlength: "2000", placeholder: "Opcional" });
  const setor = escolhaDoSetor(item);
  const parcial = reposicaoParcial(item, () => ({ comentario: comentario.value.trim() || null, setor_id: setor.select.value || null }));
  const erro = el("div", {});
  const [repus, semEstoque] = RESULTADOS.map(({ resultado, texto, classe }) => {
    const botao = el("button", { type: "button", class: classe ?? "" }, texto);
    botao.addEventListener("click", async () => {
      if (!(await confirmar(item, texto))) return;
      botoes.forEach((b) => (b.disabled = true));
      try {
        await api("POST", `/skus/${encodeURIComponent(item.sku_code)}/verificacoes`, {
          resultado,
          comentario: comentario.value.trim() || null,
          setor_id: setor.select.value || null,
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
  const botoes = [repus, semEstoque];
  return el(
    "div",
    { class: "verificar" },
    el(
      "div",
      { class: "verificar-campos" },
      el("div", {}, el("label", { for: id }, "Comentário"), comentario),
      setor.campo,
    ),
    el("div", { class: "resultados-verificacao" }, repus, parcial.abrir, semEstoque),
    parcial.formulario,
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
    el("p", { class: "frase" }, fraseDaQueda(item)),
    numerosDaQueda(item, item.disponivel),
    verificacao(item),
  );
}

function linhaDoAviso(aviso) {
  return el(
    "li",
    {},
    el("strong", {}, aviso.avisado_por),
    el("span", { class: "suave" }, ` avisou ${quando(aviso.criado_em)}`),
    aviso.pecas ? el("span", {}, ` · pediu ${numero(aviso.pecas)} ${aviso.pecas === 1 ? "peça" : "peças"}`) : null,
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
    item.queda ? el("p", { class: "frase" }, fraseDaQueda(item.queda)) : null,
    item.queda
      ? numerosDaQueda(item.queda, item.disponivel)
      : el(
          "dl",
          { class: "numeros grandes so-estoque" },
          el("div", {}, el("dt", {}, "No estoque (ERP)"), el("dd", {}, `${numero(item.disponivel)} un.`)),
        ),
    verificacao(item),
  );
}

function botaoRepus(item) {
  const erro = el("div", {});
  const botao = el("button", { type: "button", class: "primario repus" }, "Repus");
  botao.addEventListener("click", async () => {
    if (!(await confirmar(item, "Repus"))) return;
    botao.disabled = true;
    try {
      await api("POST", `/skus/${encodeURIComponent(item.sku_code)}/verificacoes`, { resultado: "repus" });
      recadoDaVerificacao = recadoDoResultado(item, "repus");
      await carregar();
    } catch (e) {
      erro.replaceChildren(mensagem("erro", `Não foi registrado: ${e.message}`));
      botao.disabled = false;
    }
  });
  const parcial = reposicaoParcial(item);
  return el(
    "div",
    { class: "verificar" },
    el("div", { class: "resultados-verificacao so-repus" }, botao, parcial.abrir),
    parcial.formulario,
    erro,
  );
}

function cartaoDeHoraDeRepor(item) {
  const r = item.reposicao;
  return el(
    "article",
    { class: "card repor hora-de-repor" },
    el(
      "div",
      { class: "repor-topo" },
      produto(item),
      el("div", { class: "selos" }, el("span", { class: "selo destaque" }, "Hora de repor"), seloDoSetor(item)),
    ),
    el("p", { class: "frase" }, fraseDaReposicao(r)),
    el(
      "dl",
      { class: "numeros grandes" },
      el("div", {}, el("dt", {}, "Na gôndola (estimado)"), el("dd", {}, numero(r.na_gondola))),
      el("div", {}, el("dt", {}, "Levar do depósito"), el("dd", {}, numero(r.a_repor))),
      el("div", {}, el("dt", {}, "No estoque (ERP)"), el("dd", {}, `${numero(item.disponivel)} un.`)),
    ),
    botaoRepus(item),
  );
}

function grupo(id, titulo, itens, cartao, seVazio) {
  return el(
    "section",
    { class: "grupo", "aria-labelledby": id },
    el(
      "header",
      {},
      el("h2", { id }, titulo),
      el("span", { class: "contagem" }, String(itens.length)),
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
        avisos,
        cartaoDeAviso,
        el("p", { class: "suave nenhum-aviso" }, "Nenhum aviso."),
      ),
      grupo(
        "t-quedas",
        "Pararam de vender e têm estoque",
        painel.quedas_de_venda,
        cartaoDeQueda,
        el("p", { class: "suave nenhum-aviso" }, "Nenhum produto parou de vender."),
      ),
      grupo(
        "t-hora-de-repor",
        "Hora de repor",
        painel.hora_de_repor,
        cartaoDeHoraDeRepor,
        el("p", { class: "suave nenhum-aviso" }, "Nenhuma gôndola perto de esvaziar."),
      ),
    ),
  );
}

let ultimaConsulta = 0;
let recadoDaVerificacao = null;

async function carregar() {
  const numeroDaConsulta = ++ultimaConsulta;
  conteudo.setAttribute("aria-busy", "true");
  try {
    const painel = await api("GET", "/reposicao/painel");
    if (numeroDaConsulta === ultimaConsulta) mostrar(painel);
  } catch (e) {
    if (numeroDaConsulta === ultimaConsulta) conteudo.replaceChildren(mensagem("erro", `Não foi possível montar o painel: ${e.message}`));
  } finally {
    if (numeroDaConsulta === ultimaConsulta) conteudo.removeAttribute("aria-busy");
  }
}

try {
  setores = await api("GET", "/setores");
  await carregar();
} catch (e) {
  conteudo.replaceChildren(mensagem("erro", `Não foi possível montar o painel: ${e.message}`));
} finally {
  carregando.remove();
}
