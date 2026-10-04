export class ErroApi extends Error {
  constructor(status, detalhes) {
    super(detalhes.map((d) => (d.campo ? `${d.campo}: ${d.mensagem}` : d.mensagem)).join("\n"));
    this.status = status;
    this.detalhes = detalhes;
  }
}

function detalhesDoErro(status, corpo) {
  const detail = corpo?.detail;
  if (typeof detail === "string") return [{ campo: null, mensagem: detail }];
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const campo = d.loc?.length > 1 ? String(d.loc[1]) : null;
      return { campo, mensagem: String(d.msg ?? "").replace(/^Value error, /, "") };
    });
  }
  return [{ campo: null, mensagem: `A API respondeu com erro ${status}.` }];
}

const PAGINA_DE_LOGIN = "login.html";
let indoParaOLogin = false;

function naPaginaDeLogin() {
  return location.pathname.endsWith(`/${PAGINA_DE_LOGIN}`);
}

function irParaOLogin() {
  if (indoParaOLogin) return;
  indoParaOLogin = true;
  location.assign(`${PAGINA_DE_LOGIN}?volta=${encodeURIComponent(location.pathname + location.search)}`);
}

export async function api(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: { Accept: "application/json", "X-Requested-With": "fetch" } };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    throw new ErroApi(0, [{ campo: null, mensagem: "Não foi possível falar com o servidor." }]);
  }
  if (resposta.status === 401 && !naPaginaDeLogin()) {
    irParaOLogin();
    return new Promise(() => {});
  }
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ErroApi(resposta.status, detalhesDoErro(resposta.status, dados));
  return dados;
}

export const TELAS = [
  { papel: "comprador", href: "index.html", rotulo: "Painel" },
  { papel: "comprador", href: "estoque.html", rotulo: "Estoque" },
  { papel: "comprador", href: "politica.html", rotulo: "Política" },
  { papel: "vendas", href: "aviso.html", rotulo: "Avisar o comprador" },
  { papel: "admin", href: "usuarios.html", rotulo: "Usuários" },
];

export function telaInicial(eu) {
  return TELAS.find((t) => eu.papeis.includes(t.papel))?.href ?? null;
}

function paginaAtual() {
  return location.pathname.split("/").pop() || "index.html";
}

export async function sair() {
  try {
    await api("POST", "/logout");
  } finally {
    location.assign(PAGINA_DE_LOGIN);
  }
}

export async function cabecalho(papelDaTela) {
  let eu;
  try {
    eu = await api("GET", "/eu");
  } catch {
    return null;
  }
  const inicio = telaInicial(eu);
  if (papelDaTela && !eu.papeis.includes(papelDaTela) && inicio) {
    location.replace(inicio);
    return eu;
  }
  const atual = paginaAtual();
  document.querySelector("header nav").replaceChildren(
    ...TELAS.filter((t) => eu.papeis.includes(t.papel)).map((t) =>
      el("a", { href: t.href, "aria-current": t.href === atual ? "page" : null }, t.rotulo),
    ),
  );
  for (const elemento of document.querySelectorAll("[data-papel]")) {
    elemento.hidden = !eu.papeis.includes(elemento.dataset.papel);
  }
  document.querySelector("header .conteudo").append(
    el(
      "div",
      { class: "sessao" },
      el("a", { class: "sessao-nome", href: "conta.html", title: "Minha conta", "aria-current": atual === "conta.html" ? "page" : null }, eu.nome),
      el("button", { type: "button", onclick: sair }, "Sair"),
    ),
  );
  return eu;
}

export function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [nome, valor] of Object.entries(atributos)) {
    if (valor === false || valor == null) continue;
    if (nome.startsWith("on")) elemento.addEventListener(nome.slice(2), valor);
    else elemento.setAttribute(nome, valor === true ? "" : valor);
  }
  elemento.append(...filhos.flat(Infinity).filter((f) => f != null && f !== false));
  return elemento;
}

export function numeros(itens) {
  return el("dl", { class: "numeros" }, itens.map(([dt, dd]) => el("div", {}, el("dt", {}, dt), el("dd", {}, dd))));
}

export function mensagem(tipo, texto) {
  return el("div", { class: `mensagem ${tipo}`, role: tipo === "erro" ? "alert" : "status" }, texto);
}

const formatoReais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function reais(centavos) {
  return formatoReais.format(centavos / 100);
}

export function numero(valor, casas = 0) {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

export function percentual(probabilidade) {
  return `${numero(probabilidade * 100)}%`;
}

export function dataHora(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

const formatoRelativo = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

export function quando(iso) {
  const minutos = Math.round((new Date(iso) - Date.now()) / 60000);
  if (Math.abs(minutos) < 1) return "agora";
  if (Math.abs(minutos) < 60) return formatoRelativo.format(minutos, "minute");
  const horas = Math.round(minutos / 60);
  if (Math.abs(horas) < 24) return formatoRelativo.format(horas, "hour");
  const dias = Math.round(horas / 24);
  if (Math.abs(dias) < 7) return formatoRelativo.format(dias, "day");
  return dataHora(iso);
}

export const MOTIVOS = {
  abaixo_do_piso_alerta: "Em ruptura",
  ruptura_antes_da_chegada: "Acaba antes da compra chegar",
  viola_teto: "Compra acima do teto",
  lead_time_observado_acima_do_contratado: "Fornecedor atrasando",
  abaixo_pedido_minimo: "Abaixo do pedido mínimo",
  periodo_sazonal: "Chega em data forte",
};

const MOTIVOS_URGENTES = ["abaixo_do_piso_alerta", "ruptura_antes_da_chegada"];

export function selosDeMotivo(motivos) {
  return motivos.map((m) => el("span", { class: MOTIVOS_URGENTES.includes(m) ? "selo urgente" : "selo destaque" }, MOTIVOS[m] ?? m));
}

export function dias(valor) {
  const arredondado = Math.round(valor * 1e6) / 1e6;
  if (arredondado > 0 && arredondado < 1) return "menos de 1 dia";
  const inteiros = Math.floor(arredondado);
  return inteiros === 1 ? "1 dia" : `${numero(inteiros)} dias`;
}

export function coberturaEmDias(valor) {
  return valor === null ? "sem giro" : dias(valor);
}

const TIPOS_DE_SINAL = {
  atraso_do_fornecedor: "Atraso do fornecedor",
  demanda_sazonal: "Demanda sazonal",
  encalhe: "Encalhe",
};

export function alertas(lista) {
  if (lista.length === 0) return null;
  return [el("h4", {}, "Alertas"), el("ul", { class: "lista" }, lista.map((a) => el("li", {}, a.mensagem)))];
}

export function sinais(lista) {
  const titulo = el("h4", {}, "Sinais do corpus");
  if (lista === null) {
    return [titulo, el("p", { class: "suave" }, "Não calculados: o Jev estava fora do ar quando a sugestão foi gerada.")];
  }
  if (lista.length === 0) return [titulo, el("p", { class: "suave" }, "Nenhum sinal encontrado nos documentos.")];
  return [
    titulo,
    el(
      "ul",
      { class: "lista" },
      lista.map((s) =>
        el(
          "li",
          {},
          el("span", { class: "selo destaque" }, TIPOS_DE_SINAL[s.tipo] ?? s.tipo),
          ` ${s.mensagem} `,
          el("span", { class: "suave" }, `(probabilidade ${percentual(s.probabilidade)})`),
          el("div", { class: "suave" }, "Trechos: ", s.trechos.map((id, i) => [i > 0 ? ", " : "", el("code", {}, id)])),
        ),
      ),
    ),
  ];
}

export const PAPEIS = {
  comprador: { rotulo: "Comprador", descricao: "painel, tela do SKU, política, preços e chat" },
  vendas: { rotulo: "Vendas", descricao: "busca de produto e avisos ao comprador" },
  reposicao: { rotulo: "Reposição", descricao: "busca de produto e painel do repositor" },
  admin: { rotulo: "Admin", descricao: "cadastro das pessoas" },
};

export function selosDePapel(papeis) {
  return papeis.map((p) => el("span", { class: "selo" }, PAPEIS[p]?.rotulo ?? p));
}

const CATEGORIAS = { felpudo: "Felpudo", jogo_cama: "Jogo de cama", mesa: "Mesa", cozinha: "Cozinha", banho: "Banho" };

export function nomeDaCategoria(categoria) {
  return CATEGORIAS[categoria] ?? categoria.replaceAll("_", " ");
}

const ESPERA_DA_BUSCA_MS = 300;

export function barraDeFiltros(formulario, aoMudar) {
  const campos = [...formulario.querySelectorAll("input[name], select[name]")];
  const limpar = formulario.querySelector(".limpar-filtros");
  const daUrl = new URLSearchParams(location.search);
  let espera;

  const valores = () => Object.fromEntries(campos.map((c) => [c.name, c.value.trim()]).filter(([, valor]) => valor));
  const atualizarLimpar = () => (limpar.hidden = Object.keys(valores()).length === 0);

  function mudou() {
    clearTimeout(espera);
    atualizarLimpar();
    aoMudar();
  }

  function limparFiltros() {
    for (const campo of campos) campo.value = "";
    mudou();
    campos[0].focus();
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    mudou();
  });
  for (const campo of campos) {
    if (campo.type === "search") {
      campo.value = daUrl.get(campo.name) ?? "";
      campo.addEventListener("input", () => {
        clearTimeout(espera);
        espera = setTimeout(mudou, ESPERA_DA_BUSCA_MS);
      });
    } else {
      campo.addEventListener("change", mudou);
    }
  }
  limpar.addEventListener("click", limparFiltros);

  return {
    valores,
    limpar: limparFiltros,
    opcoes(nome, lista) {
      const select = formulario.elements[nome];
      const valorDaUrl = daUrl.get(nome);
      if (valorDaUrl && !lista.some(([valor]) => valor === valorDaUrl)) lista.push([valorDaUrl, valorDaUrl]);
      select.append(...lista.map(([valor, rotulo]) => el("option", { value: valor }, rotulo)));
      select.value = valorDaUrl ?? "";
    },
    mostrar() {
      atualizarLimpar();
      formulario.hidden = false;
    },
  };
}

export function guardarNaUrl(parametros) {
  const consulta = new URLSearchParams(parametros).toString();
  history.replaceState(null, "", consulta ? `?${consulta}` : location.pathname);
  return consulta;
}

export const TIPOS_DE_AVISO = { acabou: "Acabou", vendendo_muito: "Vendendo muito" };

export const TIPOS_DE_DECISAO = {
  vou_comprar: "Vou comprar",
  negociando: "Negociando",
  nao_comprar_agora: "Não comprar agora",
};

export function resumoDaDecisao(d) {
  const partes = [`${TIPOS_DE_DECISAO[d.tipo] ?? d.tipo}`];
  if (d.quantidade !== null) partes.push(`${numero(d.quantidade)} un. (sugestão: ${numero(d.quantidade_sugerida)} un.)`);
  if (d.motivo) partes.push(`motivo: ${d.motivo}`);
  if (d.comentario) partes.push(d.comentario);
  return partes.join(" · ");
}
