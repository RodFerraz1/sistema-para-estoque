import { api, cabecalho, el, guardarNaUrl, mensagem, nomeDaCategoria, numero } from "./comum.js";

cabecalho("reposicao");

const ESPERA_MS = 300;
const produtoId = new URLSearchParams(location.search).get("produto")?.trim() ?? "";
const carregando = document.getElementById("carregando");

function pecas(n) {
  return `${numero(n)} ${n === 1 ? "peça" : "peças"}`;
}

function coresETamanhos(n) {
  return `${numero(n)} ${n === 1 ? "cor e tamanho" : "cores e tamanhos"}`;
}

function porDia(valor) {
  const arredondado = Math.round(valor * 10) / 10;
  return numero(arredondado, Number.isInteger(arredondado) ? 0 : 1);
}

function emEspera(funcao) {
  let espera;
  return () => {
    clearTimeout(espera);
    espera = setTimeout(funcao, ESPERA_MS);
  };
}

async function escolherProduto() {
  const secao = document.getElementById("escolher");
  const busca = document.getElementById("busca");
  const status = document.getElementById("busca-status");
  const lista = document.getElementById("produtos");
  busca.value = new URLSearchParams(location.search).get("busca") ?? "";
  let ultima = 0;

  async function buscar() {
    const consulta = guardarNaUrl(busca.value.trim() ? { busca: busca.value.trim() } : {});
    const numeroDaBusca = ++ultima;
    try {
      const produtos = await api("GET", `/reposicao/produtos?${consulta}`);
      if (numeroDaBusca !== ultima) return;
      status.textContent = produtos.length ? "" : "Nenhum produto com esse nome ou essa cor.";
      lista.replaceChildren(
        ...produtos.map((p) =>
          el(
            "li",
            {},
            el(
              "a",
              { href: `gondola.html?produto=${encodeURIComponent(p.produto_id)}` },
              el(
                "span",
                { class: "produto-gondola-nome" },
                el("strong", {}, p.produto_nome),
                el("span", { class: "suave" }, `${nomeDaCategoria(p.categoria)} · ${coresETamanhos(p.skus)}`),
              ),
              p.capacidade ? el("span", { class: "selo" }, `Cabem ${pecas(p.capacidade)}`) : null,
            ),
          ),
        ),
      );
    } catch (e) {
      if (numeroDaBusca === ultima) status.replaceChildren(mensagem("erro", `Não foi possível buscar: ${e.message}`));
    }
  }

  document.getElementById("form-busca").addEventListener("submit", (evento) => {
    evento.preventDefault();
    buscar();
  });
  busca.addEventListener("input", emEspera(buscar));
  secao.hidden = false;
  await buscar();
}

function barra(participacao) {
  const pct = Math.round(participacao * 100);
  return el(
    "div",
    { class: "participacao" },
    el("span", { class: "participacao-barra", "aria-hidden": "true" }, el("span", { style: `width: ${pct}%` })),
    el("span", { class: "participacao-valor" }, `${numero(pct)}%`),
  );
}

function linhaDoSku(s, comQuantidade) {
  return el(
    "li",
    { class: s.quantidade === 0 ? "linha-mix fora" : "linha-mix" },
    el(
      "div",
      { class: "linha-mix-info" },
      el("strong", {}, `${s.cor} · ${s.tamanho}`),
      el("code", {}, s.sku_code),
      barra(s.participacao),
      el(
        "span",
        { class: "suave" },
        `Vende ${porDia(s.venda_media_diaria)} por dia · ${s.disponivel ? `${numero(s.disponivel)} no depósito` : "sem estoque no depósito"}`,
      ),
    ),
    comQuantidade
      ? el("div", { class: "linha-mix-quantidade" }, el("b", {}, numero(s.quantidade)), el("small", {}, s.quantidade === 1 ? "peça" : "peças"))
      : null,
  );
}

function resumo(mix, comQuantidade) {
  const semVenda = mix.skus.every((s) => s.participacao === 0);
  const frases = [];
  if (semVenda) {
    frases.push(`Nenhuma venda nos últimos ${numero(mix.dias_abertos)} dias com a loja aberta: as peças são divididas igualmente entre as cores com estoque.`);
  } else {
    frases.push(`Participação nas vendas dos últimos ${numero(mix.dias_abertos)} dias com a loja aberta.`);
  }
  if (!comQuantidade) return el("p", { class: "suave" }, ...frases, " Diga quantas peças cabem para ver quantas pôr de cada cor.");
  const total = mix.skus.reduce((soma, s) => soma + s.quantidade, 0);
  return el(
    "div",
    {},
    el(
      "p",
      { class: "total-mix" },
      `Total: ${numero(total)} de ${pecas(mix.capacidade)}.`,
      total < mix.capacidade ? " Faltou estoque no depósito para encher a gôndola." : "",
    ),
    el("p", { class: "suave" }, ...frases, " Toda cor com estoque ganha ao menos uma peça quando cabe, e nada passa do que tem no depósito."),
  );
}

async function montarGondola() {
  const secao = document.getElementById("montar");
  const formulario = document.getElementById("form-capacidade");
  const campo = document.getElementById("capacidade");
  const lembrar = document.getElementById("lembrar");
  const gravada = document.getElementById("gravada");
  const conteudo = document.getElementById("mix");
  let capacidadeGravada = null;
  let primeira = true;
  let ultima = 0;
  let recado = null;

  const digitada = () => {
    const valor = Number(campo.value);
    return Number.isInteger(valor) && valor > 0 ? valor : null;
  };

  function mostrarGravada() {
    gravada.replaceChildren(
      recado ?? (capacidadeGravada ? `O Copilot lembra: cabem ${pecas(capacidadeGravada)}.` : "Grave o número para não precisar digitar da próxima vez."),
    );
    recado = null;
    lembrar.disabled = digitada() === null || digitada() === capacidadeGravada;
  }

  function mostrar(mix) {
    document.title = `Montar gôndola: ${mix.produto_nome} - Copilot de Compras`;
    document.getElementById("titulo").textContent = mix.produto_nome;
    document.getElementById("subtitulo").textContent = `${nomeDaCategoria(mix.categoria)} · ${coresETamanhos(mix.skus.length)}`;
    capacidadeGravada = mix.capacidade_gravada;
    const comQuantidade = mix.capacidade !== null;
    mostrarGravada();
    conteudo.replaceChildren(
      el(
        "section",
        { class: "card mix", "aria-labelledby": "t-mix" },
        el("h2", { id: "t-mix" }, comQuantidade ? "Pôr na gôndola" : "O que mais vende"),
        el("ol", { class: "lista-mix" }, mix.skus.map((s) => linhaDoSku(s, comQuantidade))),
        resumo(mix, comQuantidade),
      ),
    );
  }

  async function calcular() {
    const capacidade = digitada();
    const consulta = capacidade ? new URLSearchParams({ capacidade }).toString() : "";
    const numeroDoCalculo = ++ultima;
    conteudo.setAttribute("aria-busy", "true");
    try {
      const mix = await api("GET", `/reposicao/produtos/${produtoId}/mix?${consulta}`);
      if (numeroDoCalculo !== ultima) return;
      if (primeira && mix.capacidade_gravada) campo.value = mix.capacidade_gravada;
      primeira = false;
      mostrar(digitada() ? mix : { ...mix, capacidade: null });
    } catch (e) {
      if (numeroDoCalculo !== ultima) return;
      const texto = e.status === 404 ? "Este produto não tem cor nem tamanho ativo no catálogo." : `Não foi possível montar a gôndola: ${e.message}`;
      conteudo.replaceChildren(mensagem("erro", texto), el("p", {}, el("a", { href: "gondola.html" }, "Escolher outro produto")));
      formulario.hidden = true;
    } finally {
      if (numeroDoCalculo === ultima) conteudo.removeAttribute("aria-busy");
    }
  }

  campo.addEventListener("input", () => {
    lembrar.disabled = digitada() === null || digitada() === capacidadeGravada;
  });
  campo.addEventListener("input", emEspera(calcular));
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const capacidade = digitada();
    if (capacidade === null) return;
    lembrar.disabled = true;
    try {
      const salva = await api("PUT", `/reposicao/produtos/${produtoId}/capacidade`, { capacidade });
      capacidadeGravada = salva.capacidade;
      recado = mensagem("sucesso", `Gravado. Da próxima vez, a gôndola já abre com ${pecas(salva.capacidade)}.`);
      mostrarGravada();
    } catch (e) {
      gravada.replaceChildren(mensagem("erro", `Não foi gravado: ${e.message}`));
      lembrar.disabled = false;
    }
  });

  secao.hidden = false;
  await calcular();
}

try {
  await (produtoId ? montarGondola() : escolherProduto());
} finally {
  carregando.remove();
}
