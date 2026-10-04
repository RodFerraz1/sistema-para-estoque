import { api, cabecalho, el, mensagem, numero } from "./comum.js";

const formulario = document.getElementById("novo-setor");
const nome = document.getElementById("nome");
const aviso = document.getElementById("aviso");
const lista = document.getElementById("setores");

function produtos(n) {
  if (n === 0) return "Nenhum produto com este setor ainda";
  return `${numero(n)} ${n === 1 ? "produto fica" : "produtos ficam"} aqui`;
}

async function mudar(setor, campos, texto) {
  try {
    await api("PUT", `/setores/${setor.id}`, { nome: setor.nome, ativo: setor.ativo, ...campos });
    aviso.replaceChildren(mensagem("sucesso", texto));
    await carregar();
  } catch (e) {
    aviso.replaceChildren(mensagem("erro", e.message));
  }
}

function renomear(setor, linha) {
  const id = `nome-${setor.id}`;
  const campo = el("input", { id, maxlength: "100", autocomplete: "off", value: setor.nome });
  const edicao = el(
    "form",
    { class: "pessoa-edicao", novalidate: true },
    el("label", { for: id }, `Novo nome para ${setor.nome}`),
    el(
      "div",
      { class: "linha-do-formulario" },
      campo,
      el("button", { type: "submit", class: "primario" }, "Salvar"),
      el("button", { type: "button", onclick: () => edicao.remove() }, "Cancelar"),
    ),
  );
  edicao.addEventListener("submit", (evento) => {
    evento.preventDefault();
    mudar(setor, { nome: campo.value.trim() }, `${setor.nome} agora se chama ${campo.value.trim()}.`);
  });
  linha.querySelector(".pessoa-edicao")?.remove();
  linha.append(edicao);
  campo.focus();
  campo.select();
}

function linha(setor) {
  const item = el(
    "li",
    { class: setor.ativo ? "pessoa" : "pessoa desativada" },
    el("div", { class: "pessoa-quem" }, el("strong", {}, setor.nome), el("span", { class: "suave" }, produtos(setor.skus_conhecidos))),
    el("div", { class: "pessoa-situacao" }, el("div", { class: "selos" }, setor.ativo ? el("span", { class: "selo bom" }, "Ativo") : el("span", { class: "selo ruim" }, "Desativado"))),
  );
  item.append(
    el(
      "div",
      { class: "acoes" },
      el("button", { type: "button", onclick: () => renomear(setor, item) }, "Renomear"),
      el(
        "button",
        {
          type: "button",
          class: setor.ativo ? "perigo" : null,
          onclick: () =>
            mudar(
              setor,
              { ativo: !setor.ativo },
              setor.ativo
                ? `${setor.nome} saiu da lista da vendedora e do repositor. Os avisos antigos continuam com ele.`
                : `${setor.nome} voltou para a lista.`,
            ),
        },
        setor.ativo ? "Desativar" : "Reativar",
      ),
    ),
  );
  return item;
}

async function carregar() {
  try {
    const setores = await api("GET", "/setores");
    lista.replaceChildren(
      setores.length
        ? el("ul", { class: "pessoas" }, setores.map(linha))
        : el("p", { class: "suave" }, "Nenhum setor ainda. Cadastre os setores da loja acima."),
    );
  } catch (e) {
    lista.replaceChildren(mensagem("erro", `Não foi possível carregar os setores: ${e.message}`));
  }
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const valor = nome.value.trim();
  if (!valor) {
    aviso.replaceChildren(mensagem("erro", "Escreva o nome do setor."));
    return;
  }
  const botao = document.getElementById("adicionar");
  botao.disabled = true;
  try {
    const setor = await api("POST", "/setores", { nome: valor });
    formulario.reset();
    aviso.replaceChildren(mensagem("sucesso", `${setor.nome} já aparece para a vendedora e para o repositor.`));
    await carregar();
  } catch (e) {
    aviso.replaceChildren(mensagem("erro", e.message));
  } finally {
    botao.disabled = false;
  }
});

const eu = await cabecalho("admin");
if (eu?.papeis.includes("admin")) carregar();
