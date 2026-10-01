import { alertas, api, dataHora, el, guardarNome, lerNome, mensagem, numero, numeros, reais, sinais } from "./comum.js";

const STATUS = {
  pendente: { singular: "pendente", plural: "pendentes", vazio: 'Nenhuma sugestão pendente. Use "Gerar sugestões" para montar a fila.' },
  aprovada: { singular: "aprovada", plural: "aprovadas", vazio: "Nenhuma sugestão aprovada ainda." },
  rejeitada: { singular: "rejeitada", plural: "rejeitadas", vazio: "Nenhuma sugestão rejeitada ainda." },
};

const lista = document.getElementById("lista");
const contagem = document.getElementById("contagem");
const botaoGerar = document.getElementById("gerar");
const resultadoGeracao = document.getElementById("resultado-geracao");
const botoesFiltro = document.querySelectorAll(".filtro button");
let statusAtual = "pendente";

function cobertura(meses) {
  const texto = `${numero(meses, 1)} meses`;
  return meses < 0 ? `${texto} (acaba antes da chegada)` : texto;
}

function resumo(s) {
  const { sugestao } = s.sugestao;
  const { fornecedor, calculo } = sugestao;
  return numeros([
    ["Fornecedor", fornecedor.fornecedor_nome],
    ["Quantidade sugerida", `${numero(sugestao.quantidade)} un. (MOQ ${numero(fornecedor.moq_unidades)})`],
    ["Valor estimado", reais(sugestao.valor_estimado_centavos)],
    ["Cobertura na chegada sem a compra", cobertura(s.cobertura_na_chegada_sem_compra_meses)],
    ["Lead time", `${calculo.lead_time_dias} dias (${calculo.lead_time_origem})`],
  ]);
}

function faixa(f) {
  return [
    el("h4", {}, "Faixa de aprovação"),
    el("p", {}, `Faixa ${f.faixa}: ${f.aprovadores}.`, f.exige_justificativa ? " Exige justificativa." : ""),
    f.ajustes.length > 0 ? el("ul", { class: "lista suave" }, f.ajustes.map((a) => el("li", {}, a))) : null,
  ];
}

function memoriaDeCalculo(calculo) {
  return el(
    "details",
    {},
    el("summary", {}, "Memória de cálculo"),
    numeros([
      ["Giro mensal", `${numero(calculo.giro_mensal, 1)} un.`],
      ["Disponível", `${numero(calculo.disponivel)} un.`],
      ["Em trânsito", `${numero(calculo.em_transito)} un.`],
      ["Posição", `${numero(calculo.posicao)} un.`],
      ["Estoque na chegada", `${numero(calculo.estoque_na_chegada, 1)} un.`],
      ["Quantidade necessária", `${numero(calculo.qtd_necessaria)} un.`],
      ["Cobertura na chegada com a compra", `${numero(calculo.cobertura_na_chegada_meses, 1)} meses`],
    ]),
  );
}

function decisao(s) {
  if (s.status === "aprovada") {
    return el(
      "div",
      { class: "mensagem sucesso" },
      el("div", {}, `Aprovada por ${s.decidido_por} em ${dataHora(s.decidido_em)}, ${numero(s.quantidade_aprovada)} un.`),
      el("div", {}, "Pedido de compra no ERP: ", el("code", {}, s.pedido_compra_id)),
      s.justificativa ? el("div", {}, `Justificativa: ${s.justificativa}`) : null,
    );
  }
  if (s.status === "rejeitada") {
    return el(
      "div",
      { class: "mensagem erro" },
      `Rejeitada por ${s.decidido_por} em ${dataHora(s.decidido_em)}. Motivo: ${s.motivo_rejeicao}`,
    );
  }
  return null;
}

function campo(rotulo, controle, ajuda) {
  return el("div", { class: "campo" }, el("label", { for: controle.id }, rotulo), controle, ajuda ? el("p", { class: "suave" }, ajuda) : null);
}

function textoDaFaixa(f) {
  const exige = f.exige_justificativa ? "obrigatória" : "opcional";
  return [`Faixa ${f.faixa} (${f.aprovadores}): justificativa ${exige}.`, ...f.ajustes.map((a) => ` ${a}`)];
}

function formularioAprovar(s, aoDecidir) {
  const { sugestao } = s.sugestao;
  const nome = el("input", { id: `nome-a-${s.id}`, required: true, maxlength: 200, value: lerNome() });
  const quantidade = el("input", {
    id: `qtd-${s.id}`,
    type: "number",
    required: true,
    min: sugestao.fornecedor.moq_unidades,
    step: 1,
    value: sugestao.quantidade,
  });
  const justificativa = el("textarea", { id: `just-${s.id}`, maxlength: 2000, required: s.faixa.exige_justificativa });
  const ajudaJustificativa = el("p", { class: "suave", "aria-live": "polite" }, textoDaFaixa(s.faixa));
  let consultada = { quantidade: sugestao.quantidade, faixa: s.faixa };

  async function faixaDaQuantidade() {
    const n = Number(quantidade.value);
    if (n !== consultada.quantidade) {
      consultada = { quantidade: n, faixa: await api("GET", `/sugestoes/${s.id}/faixa?quantidade=${n}`) };
      justificativa.required = consultada.faixa.exige_justificativa;
      ajudaJustificativa.replaceChildren(...textoDaFaixa(consultada.faixa));
    }
    return consultada.faixa;
  }

  quantidade.addEventListener("change", async () => {
    try {
      await faixaDaQuantidade();
    } catch (e) {
      ajudaJustificativa.replaceChildren(e.message);
    }
  });

  const enviar = el("button", { type: "submit", class: "primario" }, "Confirmar aprovação");
  const formulario = el(
    "form",
    { class: "formulario" },
    campo("Seu nome", nome),
    campo("Quantidade", quantidade, `Sugerida: ${numero(sugestao.quantidade)} un. Mudar a quantidade recalcula a faixa.`),
    el("div", { class: "campo" }, el("label", { for: justificativa.id }, "Justificativa"), justificativa, ajudaJustificativa),
    el("div", { class: "acoes" }, enviar),
  );
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    guardarNome(nome.value.trim());
    const corpo = { aprovado_por: nome.value, quantidade: Number(quantidade.value) };
    if (justificativa.value.trim()) corpo.justificativa = justificativa.value;
    await aoDecidir(enviar, async () => {
      const faixa = await faixaDaQuantidade();
      if (faixa.exige_justificativa && !corpo.justificativa) {
        justificativa.focus();
        throw new Error(`Com ${numero(corpo.quantidade)} un. o pedido fica na faixa ${faixa.faixa} e exige justificativa.`);
      }
      return api("POST", `/sugestoes/${s.id}/aprovar`, corpo);
    });
  });
  return formulario;
}

function formularioRejeitar(s, aoDecidir) {
  const nome = el("input", { id: `nome-r-${s.id}`, required: true, maxlength: 200, value: lerNome() });
  const motivo = el("textarea", { id: `motivo-${s.id}`, required: true, maxlength: 2000 });
  const enviar = el("button", { type: "submit", class: "primario" }, "Confirmar rejeição");
  const formulario = el(
    "form",
    { class: "formulario" },
    campo("Seu nome", nome),
    campo("Motivo", motivo),
    el("div", { class: "acoes" }, enviar),
  );
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    guardarNome(nome.value.trim());
    await aoDecidir(enviar, () => api("POST", `/sugestoes/${s.id}/rejeitar`, { rejeitado_por: nome.value, motivo: motivo.value }));
  });
  return formulario;
}

function acoes(s, cartao) {
  const area = el("div", {});
  const erro = el("div", {});
  async function aoDecidir(botao, chamada) {
    botao.disabled = true;
    erro.replaceChildren();
    try {
      cartao.replaceWith(card(await chamada()));
      atualizarContagem();
    } catch (e) {
      erro.replaceChildren(mensagem("erro", e.message));
      botao.disabled = false;
    }
  }
  const abrir = (criar) => () => {
    erro.replaceChildren();
    area.replaceChildren(criar(s, aoDecidir));
    area.querySelector("input")?.focus();
  };
  return [
    el(
      "div",
      { class: "acoes" },
      el("button", { type: "button", class: "primario", onclick: abrir(formularioAprovar) }, "Aprovar"),
      el("button", { type: "button", onclick: abrir(formularioRejeitar) }, "Rejeitar"),
    ),
    area,
    erro,
  ];
}

function card(s) {
  const { sugestao } = s.sugestao;
  const cartao = el(
    "article",
    { class: s.destaque ? "card destaque" : "card", "data-status": s.status },
    el(
      "div",
      { class: "card-topo" },
      el("div", {}, el("h3", {}, s.produto_nome), el("code", {}, s.sku_code)),
      el("div", {}, s.destaque ? el("span", { class: "selo destaque" }, "Em destaque") : null, " ", el("span", { class: "selo" }, `Faixa ${s.faixa.faixa}`)),
    ),
    resumo(s),
    faixa(s.faixa),
    alertas(sugestao.alertas),
    sinais(s.sugestao.sinais),
    memoriaDeCalculo(sugestao.calculo),
    decisao(s),
  );
  if (s.status === "pendente") cartao.append(...acoes(s, cartao));
  return cartao;
}

function quantas(n, status) {
  return `${n} ${n === 1 ? STATUS[status].singular : STATUS[status].plural}`;
}

function atualizarContagem() {
  if (statusAtual === "pendente") contagem.textContent = quantas(lista.querySelectorAll('article[data-status="pendente"]').length, "pendente");
}

async function carregar(status) {
  statusAtual = status;
  for (const botao of botoesFiltro) botao.setAttribute("aria-pressed", String(botao.dataset.status === status));
  contagem.textContent = "Carregando...";
  lista.replaceChildren();
  try {
    const sugestoes = await api("GET", `/sugestoes?status=${status}`);
    if (status !== statusAtual) return;
    contagem.textContent = quantas(sugestoes.length, status);
    lista.replaceChildren(...(sugestoes.length ? sugestoes.map(card) : [el("p", {}, STATUS[status].vazio)]));
  } catch (e) {
    contagem.textContent = "";
    lista.replaceChildren(mensagem("erro", e.message));
  }
}

async function gerar() {
  botaoGerar.disabled = true;
  botaoGerar.textContent = "Gerando...";
  resultadoGeracao.replaceChildren(
    mensagem("aviso", "Gerando as sugestões e consultando os sinais do corpus. Com o seed, leva perto de um minuto."),
  );
  try {
    const r = await api("POST", "/sugestoes/gerar");
    resultadoGeracao.replaceChildren(
      mensagem(
        "sucesso",
        `${r.geradas} sugestões geradas de ${r.skus_avaliados} SKUs avaliados. ${r.substituidas} pendentes anteriores substituídas.`,
      ),
    );
    if (r.sinais_indisponiveis) {
      resultadoGeracao.append(mensagem("aviso", "O Jev não respondeu: as sugestões entraram sem os sinais do corpus."));
    }
    await carregar("pendente");
  } catch (e) {
    resultadoGeracao.replaceChildren(mensagem("erro", e.message));
  } finally {
    botaoGerar.disabled = false;
    botaoGerar.textContent = "Gerar sugestões";
  }
}

botaoGerar.addEventListener("click", gerar);
for (const botao of botoesFiltro) botao.addEventListener("click", () => carregar(botao.dataset.status));
carregar("pendente");
