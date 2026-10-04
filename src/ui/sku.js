import { montarChat } from "./chat.js";
import {
  TIPOS_DE_AVISO,
  alertas,
  api,
  cabecalho,
  coberturaEmDias,
  dataHora,
  dias,
  el,
  mensagem,
  numero,
  numeros,
  quando,
  reais,
  resumoDaDecisao,
  sinais,
} from "./comum.js";

cabecalho("comprador");
voltarParaOEstoque();

function voltarParaOEstoque() {
  const origem = document.referrer ? new URL(document.referrer) : null;
  if (origem?.origin !== location.origin || !origem.pathname.endsWith("/estoque.html")) return;
  const voltar = document.querySelector(".voltar");
  voltar.href = `estoque.html${origem.search}`;
  voltar.textContent = "← Estoque";
}

const MOTIVOS_SEM_COMPRA = {
  sku_novo: "SKU novo: ainda não tem o histórico mínimo de vendas que a política pede para sugerir sozinho.",
  sem_giro: "Sem giro: o SKU não vendeu nos últimos meses fechados.",
  sem_fornecedor: "Sem fornecedor ativo para o SKU.",
  acima_do_ponto_de_reposicao: "Acima do ponto de reposição: o estoque, com o que já está a caminho, ainda cobre a folga da política.",
};
const STATUS_DO_PEDIDO = {
  rascunho: "rascunho",
  aprovado: "aprovado",
  enviado: "enviado",
  recebido_parcial: "recebido em parte",
  recebido_total: "recebido",
};
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

const skuCode = new URLSearchParams(location.search).get("sku")?.trim() ?? "";
const sku = encodeURIComponent(skuCode);
const blocos = document.getElementById("blocos");

montarChat(skuCode || null);
const erro = document.getElementById("erro");

function bloco(id) {
  return document.getElementById(id);
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

async function carregar(id, pedido, mostrar) {
  try {
    const dados = await pedido;
    bloco(id).replaceChildren(el("div", {}, mostrar(dados)));
    return dados;
  } catch (e) {
    bloco(id).replaceChildren(mensagem("erro", e.message));
    throw e;
  }
}

function situacao(a) {
  document.title = `${a.produto_nome} ${a.cor} ${a.tamanho} - Copilot de Compras`;
  bloco("titulo").textContent = `${a.produto_nome}, ${a.cor}, ${a.tamanho}`;
  bloco("subtitulo").replaceChildren(el("code", {}, a.sku_code), ` · ${a.categoria.replaceAll("_", " ")}`);
  const disponivel = a.estoque.quantidade_disponivel;
  return [
    el(
      "dl",
      { class: "numeros grandes" },
      [
        ["Em estoque", `${numero(disponivel)} un.`],
        ["A caminho", `${numero(a.em_transito_unidades)} un.`],
        ["Vende por mês", `${numero(a.giro.unidades_por_mes, 1)} un.`],
        ["Segura", coberturaEmDias(a.cobertura.dias)],
      ].map(([dt, dd]) => el("div", {}, el("dt", {}, dt), el("dd", {}, dd))),
    ),
    el(
      "p",
      { class: "suave" },
      `Venda média dos últimos ${a.giro.meses_considerados} meses.`,
      a.estoque.quantidade_reservada ? ` Reservado, fora do estoque: ${numero(a.estoque.quantidade_reservada)} un.` : "",
    ),
  ];
}

function memoriaDeCalculo(c) {
  const ignorado = c.lead_time_origem === "ignorado";
  return el(
    "details",
    {},
    el("summary", {}, "Memória de cálculo"),
    numeros([
      ["Giro mensal", `${numero(c.giro_mensal, 1)} un.`],
      ["Disponível", `${numero(c.disponivel)} un.`],
      ["Em trânsito", `${numero(c.em_transito)} un.`],
      ["Posição", `${numero(c.posicao)} un.`],
      ignorado
        ? ["Lead time", "ignorado"]
        : ["Lead time", `${c.lead_time_dias} dias (${c.lead_time_origem})`],
      ignorado ? null : ["Estoque na chegada", `${numero(c.estoque_na_chegada, 1)} un.`],
      ["Quantidade necessária", `${numero(c.qtd_necessaria)} un.`],
      [ignorado ? "Cobertura com a compra" : "Cobertura na chegada com a compra", dias(c.cobertura_na_chegada_dias)],
    ].filter(Boolean)),
    ignorado
      ? el("p", { class: "suave" }, "A política não usa o prazo do fornecedor: a conta parte da posição de hoje (disponível mais o que está a caminho).")
      : null,
  );
}

function sugestao(s) {
  const resumo =
    s.quantidade > 0
      ? el(
          "div",
          { class: "sugestao-destaque" },
          el("strong", {}, `${numero(s.quantidade)} un.`),
          el("span", {}, `de ${s.fornecedor.fornecedor_nome} · ${reais(s.valor_estimado_centavos)}`),
          el("span", { class: "suave" }, `pedido mínimo ${numero(s.fornecedor.moq_unidades)} un.`),
        )
      : el(
          "div",
          { class: "sugestao-destaque" },
          el("strong", {}, "Não comprar agora"),
          el("span", {}, MOTIVOS_SEM_COMPRA[s.motivo] ?? s.motivo),
        );
  return [
    resumo,
    alertas(s.alertas),
    s.calculo ? memoriaDeCalculo(s.calculo) : null,
    el("p", { class: "suave" }, `Calculada agora com a política de compra v${s.politica_versao}.`),
  ];
}

function sinaisDoCorpus(lista) {
  return sinais(lista).slice(1);
}

function vendas(lista) {
  const maximo = Math.max(1, ...lista.map((v) => v.quantidade_unidades));
  const cronologica = [...lista].sort((a, b) => a.ano - b.ano || a.mes - b.mes);
  return [
    el(
      "div",
      { class: "grafico", role: "img", "aria-label": "Unidades vendidas por mês" },
      cronologica.map((v) =>
        el(
          "div",
          { title: `${MESES[v.mes - 1]}/${v.ano}: ${numero(v.quantidade_unidades)} un., ${reais(v.valor_total_reais)}` },
          el("b", {}, numero(v.quantidade_unidades)),
          el("span", {
            class: v.quantidade_unidades === 0 ? "barra-vertical zero" : "barra-vertical",
            style: `height: ${(v.quantidade_unidades / maximo) * 100}%`,
          }),
          el("small", {}, `${MESES[v.mes - 1]}/${String(v.ano).slice(2)}`),
        ),
      ),
    ),
    lista.some((v) => v.quantidade_unidades === 0)
      ? el("p", { class: "suave" }, "Mês sem venda pode ser ruptura: o SKU faltou na loja.")
      : null,
  ];
}

function precos(p) {
  return [
    el("h3", {}, "O que já pagamos"),
    p.historico.length
      ? tabela(
          ["Data do pedido", "Fornecedor", "Preço unitário", "Quantidade", "Pedido"],
          p.historico.map((h) => [
            dataHora(h.data),
            h.fornecedor_nome,
            reais(h.preco_unitario_centavos),
            `${numero(h.quantidade)} un.`,
            STATUS_DO_PEDIDO[h.status] ?? h.status,
          ]),
        )
      : el("p", { class: "suave" }, "Nenhum pedido de compra deste SKU no ERP."),
    el("h3", {}, "Preço atual por fornecedor"),
    p.precos_atuais.length
      ? tabela(
          ["Fornecedor", "Preço unitário", "MOQ", "Lead time"],
          p.precos_atuais.map((f) => [
            f.fornecedor_nome,
            reais(f.preco_unitario_reais),
            `${numero(f.moq_unidades)} un.`,
            `${f.lead_time_dias_observado ?? f.lead_time_dias_contratado} dias`,
          ]),
        )
      : el("p", { class: "suave" }, "Nenhum fornecedor ativo para este SKU."),
    el("h3", {}, "Substitutos (outro produto, mesma categoria e tamanho)"),
    p.substitutos.length
      ? tabela(
          ["Produto", "Menor preço atual", "Fornecedor"],
          p.substitutos.map((s) => [
            [el("a", { href: `sku.html?sku=${encodeURIComponent(s.sku_code)}` }, `${s.produto_nome}, ${s.cor}`), el("div", { class: "suave" }, s.sku_code)],
            reais(s.preco_unitario_centavos),
            s.fornecedor_nome,
          ]),
        )
      : el("p", { class: "suave" }, "Nenhum substituto com preço no catálogo."),
  ];
}

function avisos(lista) {
  if (lista.length === 0) return el("p", { class: "suave" }, "Nenhum aviso aberto.");
  return el(
    "ul",
    { class: "historico" },
    lista.map((a) =>
      el(
        "li",
        {},
        el("span", { class: "selo vendas" }, TIPOS_DE_AVISO[a.tipo] ?? a.tipo),
        el("span", { class: "suave" }, ` ${a.avisado_por}, ${quando(a.criado_em)}`),
        a.comentario ? el("div", {}, el("q", {}, a.comentario)) : null,
      ),
    ),
  );
}

function decisoes(lista) {
  if (lista.length === 0) return el("p", { class: "suave" }, "Nenhuma decisão registrada para este produto.");
  return el(
    "ul",
    { class: "historico" },
    lista.map((d) =>
      el("li", {}, el("strong", {}, resumoDaDecisao(d)), el("div", { class: "suave" }, `${d.decidido_por}, ${dataHora(d.criado_em)}`)),
    ),
  );
}

function formularioDeDecisao(sugestaoAtual) {
  const formulario = bloco("decisao-form");
  const quantidade = bloco("quantidade");
  const motivo = bloco("motivo");
  const resultado = bloco("resultado-decisao");
  const botao = bloco("registrar");

  sugestaoAtual
    .then((s) => {
      if (s.quantidade > 0) {
        quantidade.value = s.quantidade;
        bloco("ajuda-quantidade").textContent = `Sugestão do Copilot: ${numero(s.quantidade)} un. de ${s.fornecedor.fornecedor_nome} (MOQ ${numero(s.fornecedor.moq_unidades)}).`;
      } else {
        bloco("ajuda-quantidade").textContent = "O Copilot não sugere compra agora.";
      }
    })
    .catch(() => {});

  function tipo() {
    return formulario.querySelector('input[name="tipo"]:checked')?.value ?? null;
  }

  formulario.addEventListener("change", () => {
    bloco("campo-quantidade").hidden = tipo() !== "vou_comprar";
    bloco("campo-motivo").hidden = tipo() !== "nao_comprar_agora";
  });

  function faltando() {
    if (tipo() === null) return "Escolha o que você decidiu.";
    if (tipo() === "vou_comprar" && !(Number(quantidade.value) > 0)) return "Informe a quantidade que vai pedir.";
    if (tipo() === "nao_comprar_agora" && !motivo.value.trim()) return "Diga por que não vai comprar agora.";
    return null;
  }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const erroDoFormulario = faltando();
    if (erroDoFormulario) {
      resultado.replaceChildren(mensagem("erro", erroDoFormulario));
      return;
    }
    botao.disabled = true;
    try {
      await api("POST", `/skus/${sku}/decisoes`, {
        tipo: tipo(),
        quantidade: tipo() === "vou_comprar" ? Number(quantidade.value) : null,
        motivo: tipo() === "nao_comprar_agora" ? motivo.value.trim() : null,
        comentario: bloco("comentario-decisao").value.trim() || null,
      });
      location.href = "index.html";
    } catch (e) {
      resultado.replaceChildren(mensagem("erro", `A decisão não foi registrada: ${e.message}`));
      botao.disabled = false;
    }
  });
}

async function sinaisPorUltimo(principais) {
  await Promise.allSettled(principais);
  try {
    const lista = await api("GET", `/skus/${sku}/sugestao-compra/sinais`);
    bloco("sinais").replaceChildren(el("div", {}, sinaisDoCorpus(lista)));
  } catch (e) {
    const texto = e.status === 503 ? "Sinais indisponíveis: o Jev está fora do ar. O resto da tela não depende dele." : e.message;
    bloco("sinais").replaceChildren(mensagem(e.status === 503 ? "aviso" : "erro", texto));
  }
}

function semSku(texto) {
  blocos.hidden = true;
  erro.replaceChildren(mensagem("erro", texto), el("p", {}, el("a", { href: "index.html" }, "Voltar ao painel")));
}

if (!skuCode) {
  semSku("Nenhum SKU informado no link. Abra o SKU pelo painel.");
} else {
  bloco("titulo").textContent = skuCode;
  const analise = carregar("situacao", api("GET", `/skus/${sku}/analise`), situacao);
  analise.catch((e) => {
    if (e.status === 404) semSku(`O SKU ${skuCode} não existe no catálogo.`);
  });
  const sugestaoAtual = carregar("sugestao", api("GET", `/skus/${sku}/sugestao-compra`), sugestao);
  formularioDeDecisao(sugestaoAtual);
  const principais = [
    analise,
    sugestaoAtual,
    carregar("avisos", api("GET", `/skus/${sku}/avisos`), avisos),
    carregar("decisoes", api("GET", `/skus/${sku}/decisoes`), decisoes),
    carregar("precos", api("GET", `/skus/${sku}/precos`), precos),
    carregar("vendas", api("GET", `/skus/${sku}/vendas?meses=12`), vendas),
  ];
  sinaisPorUltimo(principais);
}
