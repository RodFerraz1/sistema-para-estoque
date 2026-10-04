import { TIPOS_DE_AVISO, VERIFICACAO_PARA_VENDAS, api, cabecalho, dataCurta, decisaoParaVendas, el, mensagem, numero, quando } from "./comum.js";

cabecalho("vendas");

const ESPERA_DA_BUSCA_MS = 300;

const busca = document.getElementById("busca");
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
const gondolaComentario = document.getElementById("gondola-comentario");
const enviarGondola = document.getElementById("enviar-gondola");
const resultado = document.getElementById("resultado");
const contagemMeusAvisos = document.getElementById("contagem-meus-avisos");
const listaMeusAvisos = document.getElementById("lista-meus-avisos");

const SITUACOES = {
  tem: { rotulo: "Tem", classe: "bom" },
  pouco: { rotulo: "Tem pouco", classe: "destaque" },
  acabou: { rotulo: "Acabou", classe: "urgente" },
};

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
  return el("li", {}, vem, el("span", {}, `chega por volta de ${dataCurta(entrega.previsao)}`));
}

function mostrarDisponibilidade(d) {
  disponivel = d.disponivel;
  gondolaSemEstoque.hidden = disponivel !== 0;
  const situacao = SITUACOES[d.situacao];
  disponibilidade.replaceChildren(
    el(
      "div",
      { class: "disponibilidade-topo" },
      el("span", { class: `selo ${situacao.classe}` }, situacao.rotulo),
      el("span", { class: "disponivel" }, el("strong", {}, numero(d.disponivel)), " no estoque"),
    ),
    d.entregas.length
      ? el("ul", { class: "chegadas", "aria-label": "Compras a caminho" }, d.entregas.map(chegada))
      : el("p", { class: "suave sem-chegada" }, d.disponivel === 0 ? "Nenhuma compra a caminho. Avise o comprador." : "Nenhuma compra a caminho."),
  );
}

async function consultar(s) {
  disponibilidade.hidden = false;
  disponibilidade.replaceChildren(el("p", { class: "carregando" }, "Consultando o estoque..."));
  try {
    const d = await api("GET", `/skus/${encodeURIComponent(s.sku_code)}/disponibilidade`);
    if (sku?.sku_code === s.sku_code) mostrarDisponibilidade(d);
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
  busca.hidden = true;
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
  mostrarFormulario(false);
  mostrarGondola(false);
}

async function prepararGondola(s) {
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
  busca.hidden = false;
  busca.focus();
}

async function buscar(texto) {
  const numeroDaBusca = ++ultimaBusca;
  buscaStatus.textContent = "Buscando...";
  try {
    const encontrados = await api("GET", `/skus?busca=${encodeURIComponent(texto)}`);
    if (numeroDaBusca !== ultimaBusca) return;
    buscaStatus.textContent = encontrados.length ? "" : "Nenhum produto encontrado. Tente outra palavra.";
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

formularioGondola.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!gondolaSetor.value) {
    resultado.replaceChildren(mensagem("erro", "Diga em que setor fica a gôndola vazia."));
    return;
  }
  const setor = gondolaSetor.selectedOptions[0].textContent;
  enviarGondola.disabled = true;
  try {
    await api("POST", "/avisos-gondola", {
      sku_code: sku.sku_code,
      setor_id: gondolaSetor.value,
      comentario: gondolaComentario.value.trim() || null,
    });
    resultado.replaceChildren(
      mensagem("sucesso", `Aviso enviado ao repositor: gôndola vazia de ${descricao(sku)}, no setor ${setor}. O que ele achar aparece em Meus avisos.`),
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
  const onde = aviso.para === "repositor" ? `setor ${aviso.setor} · para o repositor` : "para o comprador";
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
