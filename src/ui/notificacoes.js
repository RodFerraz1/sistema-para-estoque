import { api, coberturaEmDias, decisaoParaVendas, el, mensagem, numero, quando } from "./comum.js";

const INTERVALO_MS = 2 * 60 * 1000;
const POPUP_FECHA_EM_MS = 12 * 1000;
const CHAVE_DO_POPUP = "copilot.notificacoes-no-popup-ate";

const TIPOS = {
  ruptura: { rotulo: "Ruptura", classe: "urgente", grupo: ["SKU entrou em ruptura", "SKUs entraram em ruptura"] },
  entrega_atrasada: { rotulo: "Entrega atrasada", classe: "destaque", grupo: ["entrega atrasou", "entregas atrasaram"] },
  aviso: { rotulo: "Aviso das vendas", classe: "vendas", grupo: ["aviso da equipe de vendas", "avisos da equipe de vendas"] },
  estoque_divergente: { rotulo: "Estoque divergente", classe: "urgente", grupo: ["estoque divergente", "estoques divergentes"] },
  decisao_sobre_aviso: {
    rotulo: "Decisão do comprador",
    classe: "bom",
    grupo: ["decisão sobre o seu aviso", "decisões sobre os seus avisos"],
  },
  queda_de_venda: {
    rotulo: "Parou de vender",
    classe: "urgente",
    grupo: ["SKU parou de vender com estoque", "SKUs pararam de vender com estoque"],
  },
};

const SINO = `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>`;

function nomeDoSku(d) {
  return `${d.produto_nome}, ${d.cor}, ${d.tamanho}`;
}

function plural(n, um, varios) {
  return n === 1 ? um : varios;
}

function conteudoDe(n) {
  const d = n.detalhe;
  if (n.tipo === "ruptura") {
    return {
      href: `sku.html?sku=${encodeURIComponent(n.sku_code)}`,
      titulo: `${nomeDoSku(d)} entrou em ruptura`,
      linha: d.disponivel === 0 ? "Zerado: nada disponível" : `Segura ${coberturaEmDias(d.cobertura_dias)}, ${numero(d.disponivel)} disponíveis`,
    };
  }
  if (n.tipo === "entrega_atrasada") {
    return {
      href: `index.html#pedido-${n.pedido_id}`,
      titulo: `Entrega atrasada da ${d.fornecedor_nome}`,
      linha: `Pedido ${n.pedido_id.slice(0, 8).toUpperCase()} · ${plural(d.dias_de_atraso, "1 dia", `${numero(d.dias_de_atraso)} dias`)} de atraso · ${plural(d.skus.length, "1 SKU", `${d.skus.length} SKUs`)}`,
    };
  }
  if (n.tipo === "aviso") {
    return {
      href: `sku.html?sku=${encodeURIComponent(n.sku_code)}`,
      titulo: `${d.avisado_por} avisou: ${nomeDoSku(d)} ${d.tipo === "acabou" ? "acabou" : "está vendendo muito"}`,
      linha: d.comentario ? `"${d.comentario}"` : null,
    };
  }
  if (n.tipo === "estoque_divergente") {
    return {
      href: `sku.html?sku=${encodeURIComponent(n.sku_code)}`,
      titulo: `${d.verificado_por} não achou ${nomeDoSku(d)} no depósito`,
      linha: `O ERP dizia ${numero(d.disponivel_no_erp)} un.${d.comentario ? ` · "${d.comentario}"` : ""}`,
    };
  }
  if (n.tipo === "queda_de_venda") {
    return {
      href: `reposicao.html?busca=${encodeURIComponent(n.sku_code)}`,
      titulo: `${nomeDoSku(d)} parou de vender. Gôndola vazia?`,
      linha: `Vendia ${numero(d.venda_diaria_base, 1)} por dia, vendeu ${numero(d.vendido_na_janela)} em ${d.dias_observados} dias · ${numero(d.disponivel)} no estoque (ERP)`,
    };
  }
  if (n.tipo === "decisao_sobre_aviso") {
    return {
      href: "aviso.html#meus-avisos",
      titulo: `${d.decidido_por} decidiu sobre ${nomeDoSku(d)}`,
      linha: `${decisaoParaVendas(d).texto}${d.motivo ? ` · ${d.motivo}` : ""}`,
    };
  }
  return { href: n.sku_code ? `sku.html?sku=${encodeURIComponent(n.sku_code)}` : null, titulo: n.tipo.replaceAll("_", " "), linha: null };
}

function itemDaLista(n) {
  const tipo = TIPOS[n.tipo];
  const { href, titulo, linha } = conteudoDe(n);
  const corpo = [
    el(
      "span",
      { class: "notificacao-topo" },
      tipo ? el("span", { class: `selo ${tipo.classe}` }, tipo.rotulo) : null,
      el("span", { class: "suave" }, quando(n.aberto_em)),
      n.lida ? null : el("span", { class: "notificacao-nova" }, "Nova"),
    ),
    el("span", { class: "notificacao-titulo" }, titulo),
    linha ? el("span", { class: "suave" }, linha) : null,
  ];
  return el("li", { class: n.lida ? "notificacao" : "notificacao nao-lida" }, href ? el("a", { href }, corpo) : el("div", {}, corpo));
}

function lerDoNavegador() {
  try {
    return localStorage.getItem(CHAVE_DO_POPUP);
  } catch {
    return null;
  }
}

function gravarNoNavegador(valor) {
  try {
    localStorage.setItem(CHAVE_DO_POPUP, valor);
  } catch {
    // Sem armazenamento, o pop-up só lembra o que mostrou enquanto a página está aberta.
  }
}

export function montarSino() {
  const contagem = el("span", { class: "sino-contagem", hidden: true });
  const botao = el("button", { type: "button", class: "sino", "aria-expanded": "false", "aria-controls": "notificacoes", "aria-label": "Notificações" });
  botao.innerHTML = SINO;
  botao.append(contagem);

  const lista = el("div", { class: "notificacoes-corpo" }, el("p", { class: "suave" }, "Carregando as notificações..."));
  const marcar = el("button", { type: "button", class: "marcar-lidas", hidden: true }, "Marcar tudo como lido");
  const painel = el(
    "section",
    { id: "notificacoes", class: "notificacoes", "aria-label": "Notificações", hidden: true },
    el("div", { class: "notificacoes-topo" }, el("h2", {}, "Notificações"), marcar),
    lista,
  );
  const popup = el("div", { class: "popup-notificacoes", role: "status", "aria-live": "polite" });

  document.querySelector("header .sessao").prepend(botao);
  document.querySelector("header .conteudo").append(painel);
  document.body.append(popup);

  let mostradoNoPopupAte = lerDoNavegador();
  let ultimaConsulta = 0;
  let fecharPopup;

  function mostrarContagem(naoLidas) {
    contagem.hidden = naoLidas === 0;
    contagem.textContent = naoLidas > 99 ? "99+" : String(naoLidas);
    botao.setAttribute("aria-label", naoLidas ? `Notificações: ${naoLidas} não ${plural(naoLidas, "lida", "lidas")}` : "Notificações");
  }

  function mostrarLista(caixa) {
    marcar.hidden = caixa.nao_lidas === 0;
    lista.replaceChildren(
      caixa.notificacoes.length
        ? el("ul", { class: "notificacoes-lista" }, caixa.notificacoes.map(itemDaLista))
        : el("p", { class: "suave notificacoes-vazio" }, "Nada por aqui. Quando um SKU entrar em ruptura, uma entrega atrasar ou a equipe de vendas avisar, aparece aqui."),
    );
  }

  function abrir(aberto) {
    painel.hidden = !aberto;
    botao.setAttribute("aria-expanded", String(aberto));
    if (aberto) esconderPopup();
  }

  function esconderPopup() {
    clearTimeout(fecharPopup);
    popup.replaceChildren();
  }

  function agendarFechamento() {
    clearTimeout(fecharPopup);
    fecharPopup = setTimeout(esconderPopup, POPUP_FECHA_EM_MS);
  }

  function mostrarPopup(novas) {
    const porTipo = new Map();
    for (const n of novas) porTipo.set(n.tipo, (porTipo.get(n.tipo) ?? 0) + 1);
    popup.replaceChildren(
      el(
        "div",
        { class: "popup-cartao" },
        el(
          "div",
          { class: "popup-topo" },
          el("strong", {}, "Novidades para você"),
          el("button", { type: "button", class: "popup-fechar", "aria-label": "Fechar", onclick: esconderPopup }, "×"),
        ),
        el(
          "ul",
          { class: "popup-grupos" },
          [...porTipo].map(([tipo, n]) => {
            const t = TIPOS[tipo];
            return el("li", {}, el("span", { class: `popup-marca ${t?.classe ?? ""}` }), el("strong", {}, numero(n)), ` ${t ? plural(n, ...t.grupo) : tipo.replaceAll("_", " ")}`);
          }),
        ),
        el(
          "button",
          {
            type: "button",
            class: "primario",
            onclick: (evento) => {
              evento.stopPropagation();
              abrir(true);
            },
          },
          "Ver notificações",
        ),
      ),
    );
    agendarFechamento();
  }

  async function atualizar() {
    ultimaConsulta = Date.now();
    let caixa;
    try {
      caixa = await api("GET", "/notificacoes");
    } catch (e) {
      if (!painel.hidden) lista.replaceChildren(mensagem("erro", `Não foi possível carregar as notificações: ${e.message}`));
      return;
    }
    mostrarContagem(caixa.nao_lidas);
    mostrarLista(caixa);
    const desde = mostradoNoPopupAte ? new Date(mostradoNoPopupAte) : null;
    const novas = caixa.notificacoes.filter((n) => !n.lida && (!desde || new Date(n.aberto_em) > desde));
    if (novas.length === 0) return;
    mostradoNoPopupAte = novas.reduce((maior, n) => (new Date(n.aberto_em) > new Date(maior) ? n.aberto_em : maior), novas[0].aberto_em);
    gravarNoNavegador(mostradoNoPopupAte);
    if (painel.hidden) mostrarPopup(novas);
  }

  botao.addEventListener("click", () => abrir(painel.hidden));
  marcar.addEventListener("click", async () => {
    marcar.disabled = true;
    try {
      await api("POST", "/notificacoes/vistas");
      await atualizar();
    } finally {
      marcar.disabled = false;
    }
  });
  popup.addEventListener("mouseenter", () => clearTimeout(fecharPopup));
  popup.addEventListener("mouseleave", () => popup.firstChild && agendarFechamento());
  popup.addEventListener("focusin", () => clearTimeout(fecharPopup));
  document.addEventListener("click", (evento) => {
    if (!painel.hidden && !painel.contains(evento.target) && !botao.contains(evento.target)) abrir(false);
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && !painel.hidden) {
      abrir(false);
      botao.focus();
    }
  });
  setInterval(() => {
    if (!document.hidden) atualizar();
  }, INTERVALO_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && Date.now() - ultimaConsulta >= INTERVALO_MS) atualizar();
  });
  atualizar();
}
