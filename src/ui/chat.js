import { alertas, api, el, mensagem, numero, numeros, percentual, reais, sinais } from "./comum.js";

const INTENCOES = {
  situacao_sku: "Situação do SKU",
  sugestao_compra: "Sugestão de compra",
  politica_ou_fornecedor: "Política ou fornecedor",
  alertas_e_avisos: "Alertas e avisos",
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
  return numeros(itens);
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

const SUGESTOES = [
  "Algum vendedor pediu algum item?",
  "O que vai faltar antes da compra chegar?",
  "A Katrina costuma atrasar as entregas?",
];
const SUGESTOES_DO_SKU = ["Como está o estoque deste produto?", "Quanto devo comprar?", "Algum vendedor pediu algum item?"];

function resposta(r) {
  const temMarcas = r.resposta.search(CITACAO_NAO_CONFIRMADA) >= 0;
  return [
    textoComMarcas(r.resposta),
    temMarcas ? el("p", { class: "suave" }, "Em vermelho, citações que o Jev não confirmou no trecho citado.") : null,
    el(
      "details",
      {},
      el("summary", {}, "Como o Copilot chegou nisso"),
      secao("Entendimento", entendimento(r)),
      fichas(r.fichas),
      r.sugestoes.length ? secao("Sugestões", sugestoes(r.sugestoes)) : null,
      citacoes(r.citacoes),
      trechos(r.trechos, r.conflitos),
      el("p", { class: "suave" }, "Registro de decisão: ", el("code", {}, r.registro_id)),
    ),
  ];
}

function digitando() {
  return el("div", { class: "digitando", "aria-label": "O Copilot está respondendo" }, el("span"), el("span"), el("span"));
}

function painelDoChat(skuEmContexto) {
  const respostas = el("div", { class: "chat-respostas", "aria-live": "polite" });
  const campoPergunta = el("textarea", {
    id: "chat-pergunta",
    required: true,
    rows: 1,
    maxlength: 1000,
    "aria-label": "Pergunta",
    placeholder: skuEmContexto ? "Pergunte sobre este produto..." : "Pergunte ao Copilot...",
  });
  const botao = el("button", { type: "submit", class: "primario" }, "Enviar");
  const contexto = el(
    "p",
    { class: "chat-contexto" },
    skuEmContexto
      ? ["Falando sobre ", el("code", {}, skuEmContexto), ". Cite outro produto para mudar de assunto."]
      : "Cite o produto ou o código do SKU na pergunta.",
  );
  const boasVindas = el(
    "div",
    { class: "chat-boas-vindas" },
    el("p", {}, "Pergunte sobre estoque, quanto comprar, fornecedores, a política de compra ou os avisos das vendedoras."),
    el(
      "div",
      { class: "sugestoes-de-pergunta" },
      (skuEmContexto ? SUGESTOES_DO_SKU : SUGESTOES).map((texto) =>
        el("button", { type: "button", onclick: () => enviar(texto) }, texto),
      ),
    ),
  );
  respostas.append(boasVindas);

  async function enviar(pergunta) {
    boasVindas.remove();
    const bolha = el("div", { class: "bolha copilot" }, digitando());
    respostas.append(el("div", { class: "bolha minha" }, pergunta), bolha);
    bolha.scrollIntoView({ block: "end", behavior: "smooth" });
    botao.disabled = true;
    try {
      const enviado = skuEmContexto ? { pergunta, sku_code: skuEmContexto } : { pergunta };
      bolha.replaceChildren(el("div", {}, resposta(await api("POST", "/chat", enviado))));
    } catch (e) {
      bolha.replaceChildren(mensagem("erro", e.message));
    } finally {
      botao.disabled = false;
      bolha.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

  function ajustarAltura() {
    campoPergunta.style.height = "auto";
    campoPergunta.style.height = `${campoPergunta.scrollHeight + 2}px`;
  }

  async function perguntar(evento) {
    evento.preventDefault();
    const pergunta = campoPergunta.value.trim();
    if (!pergunta || botao.disabled) return;
    campoPergunta.value = "";
    ajustarAltura();
    await enviar(pergunta);
  }

  const formulario = el("form", { class: "chat-formulario", onsubmit: perguntar }, campoPergunta, botao);
  campoPergunta.addEventListener("input", ajustarAltura);
  campoPergunta.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      formulario.requestSubmit();
    }
  });
  return { contexto, respostas, formulario, campoPergunta };
}

const CHAVE_LARGURA = "copilot.largura-chat";
const LARGURA_MINIMA = 360;
const ESPACO_MINIMO_DA_PAGINA = 480;

function limitarLargura(largura) {
  const maxima = Math.max(LARGURA_MINIMA, window.innerWidth - ESPACO_MINIMO_DA_PAGINA);
  return Math.round(Math.min(Math.max(largura, LARGURA_MINIMA), maxima));
}

function aplicarLargura(largura) {
  document.documentElement.style.setProperty("--largura-chat", `${limitarLargura(largura)}px`);
}

function larguraGuardada() {
  try {
    return Number(localStorage.getItem(CHAVE_LARGURA)) || null;
  } catch {
    return null;
  }
}

function guardarLargura(largura) {
  try {
    localStorage.setItem(CHAVE_LARGURA, String(largura));
  } catch {}
}

function alcaDeRedimensionar(lateral) {
  const alca = el("div", {
    class: "chat-alca",
    role: "separator",
    "aria-orientation": "vertical",
    "aria-label": "Arraste para ajustar a largura do chat",
    tabindex: 0,
  });

  function larguraAtual() {
    return lateral.getBoundingClientRect().width;
  }

  alca.addEventListener("pointerdown", (evento) => {
    evento.preventDefault();
    alca.setPointerCapture(evento.pointerId);
    document.body.classList.add("redimensionando-chat");
  });
  alca.addEventListener("pointermove", (evento) => {
    if (alca.hasPointerCapture(evento.pointerId)) aplicarLargura(window.innerWidth - evento.clientX);
  });
  alca.addEventListener("pointerup", (evento) => {
    alca.releasePointerCapture(evento.pointerId);
    document.body.classList.remove("redimensionando-chat");
    guardarLargura(larguraAtual());
  });
  alca.addEventListener("dblclick", () => {
    document.documentElement.style.removeProperty("--largura-chat");
    guardarLargura("");
  });
  alca.addEventListener("keydown", (evento) => {
    const passo = { ArrowLeft: 24, ArrowRight: -24 }[evento.key];
    if (!passo) return;
    evento.preventDefault();
    aplicarLargura(larguraAtual() + passo);
    guardarLargura(larguraAtual());
  });
  return alca;
}

export function montarChat(skuEmContexto = null) {
  const abrir = document.getElementById("abrir-chat");
  const { contexto, respostas, formulario, campoPergunta } = painelDoChat(skuEmContexto);
  const fechar = el("button", { type: "button", class: "chat-fechar", "aria-label": "Fechar o chat" }, "Fechar");
  const maximizar = el("button", { type: "button", class: "chat-maximizar", "aria-pressed": "false" }, "Tela cheia");
  const lateral = el(
    "aside",
    { id: "chat-lateral", class: "chat-lateral", "aria-label": "Chat do Copilot", hidden: true },
    el("div", { class: "chat-topo" }, el("strong", {}, "Copilot"), el("div", { class: "chat-controles" }, maximizar, fechar)),
    contexto,
    respostas,
    formulario,
  );
  lateral.prepend(alcaDeRedimensionar(lateral));
  document.body.append(lateral);

  const guardada = larguraGuardada();
  if (guardada) aplicarLargura(guardada);
  window.addEventListener("resize", () => {
    const atual = larguraGuardada();
    if (atual) aplicarLargura(atual);
  });

  function alternarMaximizado(maximizado) {
    lateral.classList.toggle("maximizado", maximizado);
    document.body.classList.toggle("chat-maximizado", maximizado);
    maximizar.setAttribute("aria-pressed", String(maximizado));
    maximizar.textContent = maximizado ? "Restaurar" : "Tela cheia";
  }

  function alternar(aberto) {
    lateral.hidden = !aberto;
    abrir.setAttribute("aria-expanded", String(aberto));
    document.body.classList.toggle("com-chat", aberto);
    if (!aberto) alternarMaximizado(false);
    if (aberto) campoPergunta.focus();
    else abrir.focus();
  }

  abrir.addEventListener("click", () => alternar(lateral.hidden));
  fechar.addEventListener("click", () => alternar(false));
  maximizar.addEventListener("click", () => alternarMaximizado(!lateral.classList.contains("maximizado")));
  lateral.addEventListener("keydown", (evento) => {
    if (evento.key !== "Escape") return;
    if (lateral.classList.contains("maximizado")) alternarMaximizado(false);
    else alternar(false);
  });
}
