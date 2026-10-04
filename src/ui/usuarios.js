import { PAPEIS, api, cabecalho, el, mensagem, numeros, quando, selosDePapel } from "./comum.js";

const SEMANA_MS = 7 * 24 * 60 * 60 * 1000;

const abrirCadastro = document.getElementById("abrir-cadastro");
const cadastro = document.getElementById("cadastro");
const resultadoCadastro = document.getElementById("resultado-cadastro");
const aviso = document.getElementById("aviso");
const lista = document.getElementById("pessoas");

let eu = null;

function escolhaDePapeis(marcados = []) {
  return Object.entries(PAPEIS).map(([papel, { rotulo, descricao }]) =>
    el(
      "label",
      {},
      el("input", { type: "checkbox", value: papel, checked: marcados.includes(papel) }),
      el("span", {}, el("strong", {}, rotulo), el("small", { class: "suave" }, descricao)),
    ),
  );
}

function papeisMarcados(raiz) {
  return [...raiz.querySelectorAll('input[type="checkbox"]:checked')].map((c) => c.value);
}

function mostrarCadastro(aberto) {
  cadastro.hidden = !aberto;
  abrirCadastro.setAttribute("aria-expanded", String(aberto));
  if (aberto) document.getElementById("nome").focus();
}

abrirCadastro.addEventListener("click", () => mostrarCadastro(cadastro.hidden));
document.getElementById("cancelar-cadastro").addEventListener("click", () => mostrarCadastro(false));
document.getElementById("papeis-novos").append(...escolhaDePapeis());

cadastro.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const campos = {
    nome: document.getElementById("nome").value.trim(),
    email: document.getElementById("email").value.trim(),
    senha: document.getElementById("senha").value,
    papeis: papeisMarcados(cadastro),
  };
  if (!campos.nome || !campos.email || !campos.senha) {
    resultadoCadastro.replaceChildren(mensagem("erro", "Preencha o nome, o e-mail e a senha inicial."));
    return;
  }
  if (campos.papeis.length === 0) {
    resultadoCadastro.replaceChildren(mensagem("erro", "Escolha pelo menos um papel."));
    return;
  }
  const botao = document.getElementById("cadastrar");
  botao.disabled = true;
  try {
    const pessoa = await api("POST", "/usuarios", campos);
    cadastro.reset();
    resultadoCadastro.replaceChildren();
    mostrarCadastro(false);
    aviso.replaceChildren(mensagem("sucesso", `${pessoa.nome} já pode entrar. Passe o e-mail ${pessoa.email} e a senha inicial para a pessoa.`));
    await carregar();
  } catch (e) {
    resultadoCadastro.replaceChildren(mensagem("erro", e.message));
  } finally {
    botao.disabled = false;
  }
});

function ultimoAcesso(pessoa) {
  return pessoa.ultimo_acesso_em ? `Último acesso ${quando(pessoa.ultimo_acesso_em)}` : "Ainda não entrou";
}

function edicao(pessoa, linha, titulo, campos, salvar) {
  const resultado = el("div");
  const formulario = el(
    "form",
    { class: "pessoa-edicao", novalidate: true },
    el("strong", {}, titulo),
    campos,
    el(
      "div",
      { class: "acoes" },
      el("button", { type: "submit", class: "primario" }, "Salvar"),
      el("button", { type: "button", onclick: () => formulario.remove() }, "Cancelar"),
    ),
    resultado,
  );
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      const texto = await salvar(formulario);
      aviso.replaceChildren(mensagem("sucesso", texto));
      await carregar();
    } catch (e) {
      resultado.replaceChildren(mensagem("erro", e.message));
    }
  });
  linha.querySelector(".pessoa-edicao")?.remove();
  linha.append(formulario);
  formulario.querySelector("input")?.focus();
}

function editarPapeis(pessoa, linha) {
  edicao(pessoa, linha, `Papéis de ${pessoa.nome}`, el("div", { class: "escolhas papeis" }, escolhaDePapeis(pessoa.papeis)), async (formulario) => {
    await api("PUT", `/usuarios/${pessoa.id}/papeis`, { papeis: papeisMarcados(formulario) });
    return `Papéis de ${pessoa.nome} atualizados.`;
  });
}

function redefinirSenha(pessoa, linha) {
  const id = `senha-${pessoa.id}`;
  const campos = el(
    "div",
    { class: "campo" },
    el("label", { for: id }, "Nova senha"),
    el("input", { id, type: "text", maxlength: 200, autocomplete: "off", spellcheck: "false" }),
    el("p", { class: "suave" }, "Pelo menos 8 caracteres. Passe a nova senha para a pessoa."),
  );
  edicao(pessoa, linha, `Nova senha para ${pessoa.nome}`, campos, async (formulario) => {
    await api("PUT", `/usuarios/${pessoa.id}/senha`, { senha: formulario.querySelector("input").value });
    return `Senha de ${pessoa.nome} redefinida. A pessoa já pode entrar com a nova senha.`;
  });
}

async function mudarSituacao(pessoa) {
  if (pessoa.ativo && !confirm(`Desativar ${pessoa.nome}? A pessoa sai de todos os aparelhos e não entra mais. O que ela registrou continua no histórico.`)) {
    return;
  }
  try {
    await (pessoa.ativo ? api("POST", `/usuarios/${pessoa.id}/desativar`) : api("POST", `/usuarios/${pessoa.id}/reativar`));
    aviso.replaceChildren(mensagem("sucesso", pessoa.ativo ? `${pessoa.nome} não entra mais e saiu de todos os aparelhos.` : `${pessoa.nome} pode entrar de novo.`));
    await carregar();
  } catch (e) {
    aviso.replaceChildren(mensagem("erro", e.message));
  }
}

function linha(pessoa) {
  const souEu = pessoa.id === eu.id;
  const item = el(
    "li",
    { class: pessoa.ativo ? "pessoa" : "pessoa desativada" },
    el(
      "div",
      { class: "pessoa-quem" },
      el("strong", {}, pessoa.nome, souEu ? el("span", { class: "suave" }, " (você)") : null),
      el("span", { class: "suave" }, pessoa.email),
    ),
    el(
      "div",
      { class: "pessoa-situacao" },
      el("div", { class: "selos" }, pessoa.ativo ? el("span", { class: "selo bom" }, "Ativa") : el("span", { class: "selo ruim" }, "Desativada"), selosDePapel(pessoa.papeis)),
      el("span", { class: "suave" }, ultimoAcesso(pessoa)),
    ),
  );
  item.append(
    el(
      "div",
      { class: "acoes" },
      el("button", { type: "button", onclick: () => editarPapeis(pessoa, item) }, "Editar papéis"),
      el("button", { type: "button", onclick: () => redefinirSenha(pessoa, item) }, "Redefinir senha"),
      souEu ? null : el("button", { type: "button", class: pessoa.ativo ? "perigo" : null, onclick: () => mudarSituacao(pessoa) }, pessoa.ativo ? "Desativar" : "Reativar"),
    ),
  );
  return item;
}

async function carregar() {
  try {
    const pessoas = await api("GET", "/usuarios");
    const ativas = pessoas.filter((p) => p.ativo);
    const naSemana = ativas.filter((p) => p.ultimo_acesso_em && Date.now() - new Date(p.ultimo_acesso_em) < SEMANA_MS);
    document.getElementById("resumo").replaceChildren(
      el(
        "div",
        { class: "card" },
        numeros([
          ["Pessoas ativas", String(ativas.length)],
          ["Entraram nos últimos 7 dias", String(naSemana.length)],
          ["Desativadas", String(pessoas.length - ativas.length)],
        ]),
      ),
    );
    document.querySelector("#resumo .numeros").classList.add("grandes");
    lista.replaceChildren(el("ul", { class: "pessoas" }, pessoas.map(linha)));
  } catch (e) {
    lista.replaceChildren(mensagem("erro", `Não foi possível carregar as pessoas: ${e.message}`));
  }
}

eu = await cabecalho("admin");
if (eu?.papeis.includes("admin")) carregar();
