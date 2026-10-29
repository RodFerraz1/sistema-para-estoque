import { api, cabecalho, el, numero } from "./comum.js";

cabecalho("reposicao");

const ATUALIZAR_A_CADA_MS = 60 * 1000;

const PRIORIDADES = {
  mais_de_um_motivo: { rotulo: "Mais de um motivo", plural: "Mais de um motivo", classe: "urgente" },
  parou_de_vender: { rotulo: "Parou de vender", plural: "Pararam de vender", classe: "destaque" },
  gondola_vazia: { rotulo: "Gôndola vazia", plural: "Gôndolas vazias", classe: "vendas" },
  hora_de_repor: { rotulo: "Hora de repor", plural: "Hora de repor", classe: "rotina" },
};

const carregando = document.getElementById("carregando");
const lista = document.getElementById("gondolas");
const resumo = document.getElementById("resumo");
const atualizado = document.getElementById("atualizado");

function hora(data) {
  return data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function quantidade(g) {
  if (g.a_repor == null) {
    return el(
      "div",
      { class: "gondola-quantidade sem-capacidade" },
      el("b", {}, "Encher a gôndola"),
      el("small", {}, `${numero(g.disponivel)} no estoque`),
    );
  }
  return el(
    "div",
    { class: "gondola-quantidade" },
    el("b", {}, numero(g.a_repor)),
    el("small", {}, g.a_repor === 1 ? "peça a repor" : "peças a repor"),
  );
}

function cartao(g) {
  const prioridade = PRIORIDADES[g.prioridade];
  return el(
    "li",
    { class: `gondola-cartao ${prioridade.classe}` },
    el("span", { class: "visualmente-oculto" }, `${prioridade.rotulo}.`),
    el("span", { class: "gondola-setor" }, g.setor?.nome ?? "Setor não informado"),
    el("code", { class: "gondola-sku" }, g.sku_code),
    el("strong", { class: "gondola-nome" }, g.produto_nome),
    el("span", { class: "gondola-variante" }, `${g.cor} · ${g.tamanho}`),
    quantidade(g),
  );
}

function mostrarResumo(gondolas) {
  resumo.replaceChildren(
    ...Object.entries(PRIORIDADES).map(([chave, prioridade]) => {
      const quantas = gondolas.filter((g) => g.prioridade === chave).length;
      return el(
        "li",
        { class: `dashboard-contador ${prioridade.classe}${quantas ? "" : " zerado"}` },
        el("b", {}, numero(quantas)),
        el("span", {}, quantas === 1 ? prioridade.rotulo : prioridade.plural),
      );
    }),
  );
}

function mostrar(gondolas) {
  mostrarResumo(gondolas);
  if (!gondolas.length) {
    lista.replaceChildren(
      el(
        "li",
        { class: "dashboard-em-dia" },
        el("strong", {}, "Todas as gôndolas em dia"),
        el("span", {}, "Quando um produto parar de vender, uma vendedora avisar ou chegar a hora de repor, ele aparece aqui."),
      ),
    );
    return;
  }
  lista.replaceChildren(...gondolas.map(cartao));
}

async function atualizar() {
  try {
    mostrar(await api("GET", "/reposicao/dashboard"));
    atualizado.classList.remove("sem-conexao");
    atualizado.textContent = `Atualiza sozinho a cada minuto. Última atualização às ${hora(new Date())}.`;
  } catch (e) {
    atualizado.classList.add("sem-conexao");
    const ultima = atualizado.dataset.ultima;
    atualizado.textContent = `Não foi possível atualizar: ${e.message}${ultima ? ` Mostrando o que havia às ${ultima}.` : ""}`;
    return;
  } finally {
    carregando.remove();
  }
  atualizado.dataset.ultima = hora(new Date());
}

function montarTelaCheia() {
  const botao = document.getElementById("tela-cheia");
  if (!document.fullscreenEnabled) {
    botao.hidden = true;
    return;
  }
  botao.addEventListener("click", () =>
    document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(),
  );
  document.addEventListener("fullscreenchange", () => {
    botao.textContent = document.fullscreenElement ? "Sair da tela cheia" : "Tela cheia";
  });
}

montarTelaCheia();
await atualizar();
setInterval(atualizar, ATUALIZAR_A_CADA_MS);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") atualizar();
});
