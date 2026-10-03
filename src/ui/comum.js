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

export function lerNome(chave = "copilot.nome") {
  try {
    return localStorage.getItem(chave) ?? "";
  } catch {
    return "";
  }
}

export function guardarNome(nome, chave = "copilot.nome") {
  try {
    localStorage.setItem(chave, nome);
  } catch {}
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
