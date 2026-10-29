import { TIPOS_DE_AVISO, VERIFICACAO_PARA_VENDAS, api, cabecalho, dataCurta, decisaoParaVendas, el, mensagem, numero, quando } from "./comum.js";
import { lerCodigoDeBarras } from "./leitor.js";

cabecalho("vendas");

const ESPERA_DA_BUSCA_MS = 300;

const buscaLinha = document.getElementById("busca-linha");
const busca = document.getElementById("busca");
const abrirLeitor = document.getElementById("abrir-leitor");
const buscaStatus = document.getElementById("busca-status");
const resultados = document.getElementById("resultados");
const escolhido = document.getElementById("escolhido");
const disponibilidade = document.getElementById("disponibilidade");
const acoes = document.getElementById("acoes");
const abrirAviso = document.getElementById("abrir-aviso");
const formulario = document.getElementById("aviso-form");
const botoesTipo = document.querySelectorAll(".tipos button");
const comentario = document.getElementById("comentario");
const enviar = document.getElementById("enviar");
const abrirGondola = document.getElementById("abrir-gondola");
const formularioGondola = document.getElementById("gondola-form");
const gondolaSemEstoque = document.getElementById("gondola-sem-estoque");
const gondolaSetor = document.getElementById("gondola-setor");
const gondolaSetorDica = document.getElementById("gondola-setor-dica");
const gondolaPecas = document.getElementById("gondola-pecas");
const gondolaPecasDica = document.getElementById("gondola-pecas-dica");
const gondolaComentario = document.getElementById("gondola-comentario");
const enviarGondola = document.getElementById("enviar-gondola");
const resultado = document.getElementById("resultado");
const confirmarRepetido = document.getElementById("confirmar-repetido");
const quemJaAvisou = document.getElementById("quem-ja-avisou");
const contagemMeusAvisos = document.getElementById("contagem-meus-avisos");
const listaMeusAvisos = document.getElementById("lista-meus-avisos");
const dialogoCompras = document.getElementById("compras");
const comprasProduto = document.getElementById("compras-produto");
const comprasTabela = document.getElementById("compras-tabela");

let sku = null;
let disponivel = null;
let setoresAtivos = null;
let tipo = null;
let espera = null;
let ultimaBusca = 0;

function descricao(s) {
  return `${s.produto_nome}, ${s.cor}, ${s.tamanho}`;
}

function unidades(n) {
  return `${numero(n)} ${n === 1 ? "unidade" : "unidades"}`;
}

function chegada(entrega) {
  const vem = el("strong", {}, `Vem ${unidades(entrega.quantidade)}`);
  if (entrega.previsao === null) return el("li", {}, vem, el("span", { class: "suave" }, "ainda sem data prevista"));
  if (entrega.atrasada) {
    return el(
      "li",
      { class: "atrasada" },
      vem,
      el("span", {}, el("span", { class: "selo urgente" }, "Atrasada"), ` era para ${dataCurta(entrega.previsao)}`),
    );
  }
  return el("li", {}, vem, el("span", {}, `chegada prevista para ${dataCurta(entrega.previsao)}`));
}

function mostrarDisponibilidade(d) {
  disponivel = d.disponivel;
  gondolaSemEstoque.hidden = disponivel !== 0;
  disponibilidade.replaceChildren(
    el(
      "div",
      { class: "disponibilidade-topo" },
      el("span", {}, "Quantidade em estoque"),
      el("span", { class: "disponivel" }, el("strong", {}, numero(d.disponivel)), d.disponivel === 1 ? " unidade" : " unidades"),
    ),
    d.entregas.length
      ? el("ul", { class: "chegadas", "aria-label": "Compras a caminho" }, d.entregas.map(chegada))
      : el("p", { class: "suave sem-chegada" }, d.disponivel === 0 ? "Nenhuma compra a caminho. Avise o comprador." : "Nenhuma compra a caminho."),
  );
}

function quantas(n, singular, plural) {
  return `${n} ${n === 1 ? singular : plural}`;
}


const CAMINHAO = `<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" fill="currentColor"><path d="M1 5.5A1.5 1.5 0 0 1 2.5 4h11A1.5 1.5 0 0 1 15 5.5V8h3.4a1.5 1.5 0 0 1 1.2.6l2.9 3.8a1.5 1.5 0 0 1 .3.9v3.2a1.5 1.5 0 0 1-1.5 1.5h-.9a3 3 0 0 0-5.8 0H9.4a3 3 0 0 0-5.8 0h-.1A1.5 1.5 0 0 1 2 16.5Zm15 4.5v3h4.6l-2.3-3Z"/><circle cx="6.5" cy="18" r="2"/><circle cx="17.5" cy="18" r="2"/></svg>`;

function previsaoNaTabela(c) {
  if (c.previsao === null) return el("span", { class: "suave" }, "sem data");
  if (!c.atrasada) return dataCurta(c.previsao);
  return el("span", {}, `${dataCurta(c.previsao)} `, el("span", { class: "selo urgente" }, "Atrasada"));
}

function variam(compras, campo) {
  return new Set(compras.map((c) => c[campo])).size > 1;
}

// "5 cores", "3 tamanhos" ou "8 variações", conforme o que muda entre os SKUs que vêm.
function variacoes(compras) {
  const skus = new Set(compras.map((c) => c.sku_code)).size;
  if (variam(compras, "gramatura") || (variam(compras, "cor") && variam(compras, "tamanho"))) {
    return quantas(skus, "variação", "variações");
  }
  if (variam(compras, "tamanho")) return quantas(skus, "tamanho", "tamanhos");
  return quantas(skus, "cor", "cores");
}

function abrirCompras(s, compras) {
  comprasProduto.textContent = s.produto_nome;
  comprasTabela.replaceChildren(
    el(
      "table",
      {},
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          el("th", { scope: "col" }, "Cor"),
          el("th", { scope: "col", class: "quantidade" }, "Qtd."),
          el("th", { scope: "col" }, "Previsão"),
        ),
      ),
      el(
        "tbody",
        {},
        compras.map((c) =>
          el(
            "tr",
            { class: c.sku_code === s.sku_code ? "atual" : null, title: c.sku_code === s.sku_code ? "O produto que você está vendo" : null },
            el("td", {}, c.cor),
            el("td", { class: "quantidade" }, numero(c.quantidade)),
            el("td", {}, previsaoNaTabela(c)),
          ),
        ),
      ),
    ),
  );
  dialogoCompras.showModal();
}

async function mostrarComprasDoProduto(s) {
  let compras;
  try {
    compras = await api("GET", `/skus/${encodeURIComponent(s.sku_code)}/compras-do-produto`);
  } catch {
    return;
  }
  if (sku?.sku_code !== s.sku_code || compras.length === 0) return;
  const pecas = compras.reduce((total, c) => total + c.quantidade, 0);
  const icone = el("span", { class: "caminhao" });
  icone.innerHTML = CAMINHAO;
  disponibilidade.append(
    el(
      "button",
      { type: "button", class: "pedidos-a-caminho", "aria-haspopup": "dialog", onclick: () => abrirCompras(s, compras) },
      icone,
      el("span", {}, "Pedidos a caminho", el("small", {}, `${variacoes(compras)} · ${numero(pecas)} peças`)),
      el("span", { class: "seta", "aria-hidden": "true" }, "›"),
    ),
  );
}

async function consultar(s) {
  disponibilidade.hidden = false;
  disponibilidade.replaceChildren(el("p", { class: "carregando" }, "Consultando o estoque..."));
  try {
    const d = await api("GET", `/skus/${encodeURIComponent(s.sku_code)}/disponibilidade`);
    if (sku?.sku_code !== s.sku_code) return;
    mostrarDisponibilidade(d);
    mostrarComprasDoProduto(s);
  } catch (e) {
    if (sku?.sku_code === s.sku_code) disponibilidade.replaceChildren(mensagem("erro", `Não foi possível consultar o estoque: ${e.message}`));
  }
}

function escolher(s) {
  sku = s;
  resultados.replaceChildren();
  buscaStatus.textContent = "";
  resultado.replaceChildren();
  busca.value = "";
  buscaLinha.hidden = true;
  escolhido.replaceChildren(
    el("div", {}, el("strong", {}, descricao(s)), el("div", { class: "suave" }, s.sku_code)),
    el("button", { type: "button", onclick: trocar }, "Trocar"),
  );
  escolhido.hidden = false;
  acoes.hidden = false;
  consultar(s);
}

function mostrarFormulario(aberto) {
  formulario.hidden = !aberto;
  abrirAviso.setAttribute("aria-expanded", String(aberto));
  if (aberto) mostrarGondola(false);
}

function mostrarGondola(aberto) {
  formularioGondola.hidden = !aberto;
  abrirGondola.setAttribute("aria-expanded", String(aberto));
  if (aberto) mostrarFormulario(false);
}

function limparFormulario() {
  tipo = null;
  for (const botao of botoesTipo) botao.setAttribute("aria-pressed", "false");
  comentario.value = "";
  gondolaComentario.value = "";
  gondolaPecas.value = "";
  mostrarFormulario(false);
  mostrarGondola(false);
}

function pecas(n) {
  return quantas(n, "peça", "peças");
}

// A sugestão é a parte do SKU no mix de gôndola: a capacidade dividida pelo que cada cor vende.
function mostrarSugestao(sugestao) {
  gondolaPecas.value = sugestao.pecas || "";
  if (sugestao.pecas) {
    gondolaPecasDica.textContent = `Sugestão: ${pecas(sugestao.pecas)}, a parte desta cor nos ${numero(sugestao.capacidade)} lugares da gôndola, pelo que ela vende. Mude se a gôndola pedir outra quantidade.`;
  } else if (sugestao.capacidade === null) {
    gondolaPecasDica.textContent = "Sem sugestão: o repositor ainda não disse quantas peças deste produto cabem na gôndola. Se souber, diga quantas levar.";
  } else if (sugestao.disponivel > 0) {
    gondolaPecasDica.textContent = "Sem sugestão: pelo que vende, esta cor não ganha lugar na gôndola. Se precisar, diga quantas levar.";
  } else {
    gondolaPecasDica.textContent = "";
  }
}

async function prepararSugestao(s) {
  gondolaPecas.value = "";
  gondolaPecasDica.textContent = "Calculando quantas peças levar...";
  try {
    const sugestao = await api("GET", `/skus/${encodeURIComponent(s.sku_code)}/sugestao-gondola`);
    if (sku?.sku_code === s.sku_code) mostrarSugestao(sugestao);
  } catch {
    if (sku?.sku_code === s.sku_code) gondolaPecasDica.textContent = "Não foi possível calcular a sugestão. Se souber, diga quantas levar.";
  }
}

async function prepararGondola(s) {
  prepararSugestao(s);
  gondolaSetor.disabled = true;
  gondolaSetorDica.hidden = true;
  gondolaSetor.replaceChildren(el("option", { value: "" }, "Carregando os setores..."));
  try {
    const [setores, conhecido] = await Promise.all([
      setoresAtivos ?? api("GET", "/setores"),
      api("GET", `/skus/${encodeURIComponent(s.sku_code)}/setor`),
    ]);
    setoresAtivos = setores;
    if (sku?.sku_code !== s.sku_code) return;
    const sabido = conhecido.setor?.ativo ? conhecido.setor.id : "";
    gondolaSetor.replaceChildren(
      sabido ? null : el("option", { value: "" }, "Escolha o setor"),
      ...setores.map((setor) => el("option", { value: setor.id }, setor.nome)),
    );
    gondolaSetor.value = sabido;
    gondolaSetorDica.hidden = Boolean(sabido);
    gondolaSetor.disabled = false;
  } catch (e) {
    if (sku?.sku_code === s.sku_code) resultado.replaceChildren(mensagem("erro", `Não foi possível carregar os setores: ${e.message}`));
  }
}

function trocar() {
  sku = null;
  disponivel = null;
  escolhido.hidden = true;
  disponibilidade.hidden = true;
  acoes.hidden = true;
  limparFormulario();
  buscaLinha.hidden = false;
  busca.focus();
}

function soNumeros(texto) {
  return /^\d+$/.test(texto);
}

// `direto`: a vendedora leu o código de barras ou apertou Enter. Com um produto só, ele já
// fica escolhido, sem um toque a mais.
async function buscar(texto, direto = false) {
  const numeroDaBusca = ++ultimaBusca;
  buscaStatus.textContent = "Buscando...";
  try {
    const encontrados = await api("GET", `/skus?busca=${encodeURIComponent(texto)}`);
    if (numeroDaBusca !== ultimaBusca) return;
    if (direto && encontrados.length === 1) return escolher(encontrados[0]);
    buscaStatus.textContent = encontrados.length
      ? ""
      : soNumeros(texto)
        ? `Nenhum produto com o código ${texto}. Confira os números ou busque pelo nome.`
        : "Nenhum produto encontrado. Tente outra palavra.";
    resultados.replaceChildren(
      ...encontrados.map((s) =>
        el(
          "li",
          {},
          el(
            "button",
            { type: "button", onclick: () => escolher(s) },
            el("strong", {}, s.produto_nome),
            el("span", {}, `${s.cor}, ${s.tamanho}`),
            el("span", { class: "suave" }, s.sku_code),
          ),
        ),
      ),
    );
  } catch (e) {
    if (numeroDaBusca === ultimaBusca) buscaStatus.textContent = e.message;
  }
}

busca.addEventListener("input", () => {
  clearTimeout(espera);
  resultado.replaceChildren();
  const texto = busca.value.trim();
  if (texto.length < 2) {
    ultimaBusca++;
    resultados.replaceChildren();
    buscaStatus.textContent = "";
    return;
  }
  espera = setTimeout(() => buscar(texto), ESPERA_DA_BUSCA_MS);
});

// Leitor de mão (USB ou Bluetooth) digita os números e aperta Enter, como um teclado.
busca.addEventListener("keydown", (evento) => {
  if (evento.key !== "Enter") return;
  evento.preventDefault();
  clearTimeout(espera);
  const texto = busca.value.trim();
  if (texto.length >= 2) buscar(texto, true);
});

abrirLeitor.addEventListener("click", async () => {
  const codigo = await lerCodigoDeBarras();
  if (codigo === null) return busca.focus();
  clearTimeout(espera);
  resultado.replaceChildren();
  busca.value = codigo;
  buscar(codigo, true);
});

abrirAviso.addEventListener("click", () => {
  mostrarFormulario(formulario.hidden);
  if (!formulario.hidden) botoesTipo[0].focus();
});

abrirGondola.addEventListener("click", () => {
  const abrir = formularioGondola.hidden;
  mostrarGondola(abrir);
  if (abrir) {
    gondolaSemEstoque.hidden = disponivel !== 0;
    prepararGondola(sku).then(() => gondolaSetor.focus());
  }
});

async function avisosAbertos(s) {
  try {
    return await api("GET", `/skus/${encodeURIComponent(s.sku_code)}/avisos-gondola`);
  } catch {
    return [];
  }
}

function confirmarAvisoRepetido(avisos) {
  quemJaAvisou.replaceChildren(
    ...avisos.map((a) => el("li", {}, el("strong", {}, a.meu ? "Você" : a.avisado_por), ` avisou ${quando(a.criado_em)}`)),
  );
  confirmarRepetido.showModal();
  return new Promise((resolve) => {
    const fim = new AbortController();
    const responder = (avisar) => {
      fim.abort();
      resolve(avisar);
    };
    confirmarRepetido.addEventListener("submit", (e) => responder(e.submitter?.value === "avisar"), { signal: fim.signal });
    confirmarRepetido.addEventListener("cancel", () => responder(false), { signal: fim.signal });
  });
}

formularioGondola.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!gondolaSetor.value) {
    resultado.replaceChildren(mensagem("erro", "Diga em que setor fica a gôndola vazia."));
    return;
  }
  if (gondolaPecas.value && !gondolaPecas.checkValidity()) {
    resultado.replaceChildren(mensagem("erro", "Diga quantas peças levar com um número inteiro de 1 a 10.000, ou deixe em branco."));
    return;
  }
  const setor = gondolaSetor.selectedOptions[0].textContent;
  const pedidas = gondolaPecas.value ? Number(gondolaPecas.value) : null;
  enviarGondola.disabled = true;
  try {
    const abertos = await avisosAbertos(sku);
    if (abertos.length && !(await confirmarAvisoRepetido(abertos))) return;
    await api("POST", "/avisos-gondola", {
      sku_code: sku.sku_code,
      setor_id: gondolaSetor.value,
      comentario: gondolaComentario.value.trim() || null,
      pecas: pedidas,
    });
    const levar = pedidas ? `, levar ${pecas(pedidas)}` : "";
    resultado.replaceChildren(
      mensagem("sucesso", `Aviso enviado ao repositor: gôndola vazia de ${descricao(sku)}, no setor ${setor}${levar}. O que ele achar aparece em Meus avisos.`),
    );
    trocar();
    carregarMeusAvisos();
  } catch (e) {
    resultado.replaceChildren(mensagem("erro", `O aviso não foi enviado: ${e.message}`));
  } finally {
    enviarGondola.disabled = false;
  }
});

for (const botao of botoesTipo) {
  botao.addEventListener("click", () => {
    tipo = botao.dataset.tipo;
    for (const outro of botoesTipo) outro.setAttribute("aria-pressed", String(outro === botao));
  });
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (tipo === null) {
    resultado.replaceChildren(mensagem("erro", "Diga se acabou ou se está vendendo muito."));
    return;
  }
  enviar.disabled = true;
  try {
    const aviso = await api("POST", "/avisos", {
      sku_code: sku.sku_code,
      tipo,
      comentario: comentario.value.trim() || null,
    });
    resultado.replaceChildren(
      mensagem("sucesso", `Aviso enviado ao comprador: ${descricao(sku)}, ${TIPOS_DE_AVISO[aviso.tipo].toLowerCase()}. A resposta dele aparece em Meus avisos.`),
    );
    trocar();
    carregarMeusAvisos();
  } catch (e) {
    resultado.replaceChildren(mensagem("erro", `O aviso não foi enviado: ${e.message}`));
  } finally {
    enviar.disabled = false;
  }
});

function desfechoDaGondola(aviso) {
  const v = aviso.verificacao;
  if (v === null) {
    return el("div", { class: "desfecho" }, el("span", { class: "selo vendas" }, "Aguardando o repositor"));
  }
  const { texto, classe } = VERIFICACAO_PARA_VENDAS[v.resultado];
  return el(
    "div",
    { class: "desfecho" },
    el("span", { class: `selo ${classe}` }, texto),
    el("span", { class: "suave" }, `verificou ${quando(v.criado_em)}`),
    v.comentario ? el("p", { class: "motivo" }, `Repositor: "${v.comentario}"`) : null,
  );
}

function desfecho(aviso) {
  if (aviso.para === "repositor") return desfechoDaGondola(aviso);
  if (aviso.decisao === null) {
    return el("div", { class: "desfecho" }, el("span", { class: "selo vendas" }, "Aguardando o comprador"));
  }
  const { texto, classe } = decisaoParaVendas(aviso.decisao);
  return el(
    "div",
    { class: "desfecho" },
    el("span", { class: `selo ${classe}` }, texto),
    el("span", { class: "suave" }, `decidiu ${quando(aviso.decisao.criado_em)}`),
    aviso.decisao.motivo ? el("p", { class: "motivo" }, `Motivo: ${aviso.decisao.motivo}`) : null,
  );
}

function cartaoDoAviso(aviso) {
  const aguardando = aviso.para === "repositor" ? aviso.verificacao === null : aviso.decisao === null;
  const pediu = aviso.pecas ? ` · pediu ${pecas(aviso.pecas)}` : "";
  const onde = aviso.para === "repositor" ? `setor ${aviso.setor}${pediu} · para o repositor` : "para o comprador";
  return el(
    "article",
    { class: `card meu-aviso${aguardando ? " aguardando" : ""}` },
    el(
      "div",
      { class: "meu-aviso-topo" },
      el("strong", {}, `${TIPOS_DE_AVISO[aviso.tipo]}: ${aviso.produto_nome}`),
      el("span", { class: "suave" }, quando(aviso.criado_em)),
    ),
    el("div", { class: "suave" }, `${aviso.cor} · ${aviso.tamanho} · ${onde}`),
    aviso.comentario ? el("p", { class: "comentario-do-aviso" }, `"${aviso.comentario}"`) : null,
    desfecho(aviso),
  );
}

async function carregarMeusAvisos() {
  try {
    const avisos = await api("GET", "/avisos/meus");
    contagemMeusAvisos.textContent = String(avisos.length);
    contagemMeusAvisos.hidden = avisos.length === 0;
    listaMeusAvisos.replaceChildren(
      avisos.length
        ? el("div", { class: "itens" }, avisos.map(cartaoDoAviso))
        : el(
            "div",
            { class: "card vazio" },
            el("strong", {}, "Nenhum aviso nos últimos 30 dias"),
            el("p", { class: "suave" }, "Quando você avisar o comprador ou o repositor, o aviso aparece aqui com o que ele fez."),
          ),
    );
  } catch (e) {
    listaMeusAvisos.replaceChildren(mensagem("erro", `Não foi possível carregar os seus avisos: ${e.message}`));
  }
}

carregarMeusAvisos();
