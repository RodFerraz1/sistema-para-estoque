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

export async function api(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: { Accept: "application/json" } };
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
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ErroApi(resposta.status, detalhesDoErro(resposta.status, dados));
  return dados;
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

export function lerNome() {
  try {
    return localStorage.getItem("copilot.nome") ?? "";
  } catch {
    return "";
  }
}

export function guardarNome(nome) {
  try {
    localStorage.setItem("copilot.nome", nome);
  } catch {}
}
