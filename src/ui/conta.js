import { api, cabecalho, el, mensagem, sair, selosDePapel } from "./comum.js";

const formulario = document.getElementById("senha-form");
const senhaAtual = document.getElementById("senha-atual");
const novaSenha = document.getElementById("nova-senha");
const repetir = document.getElementById("repetir-senha");
const trocar = document.getElementById("trocar");
const resultado = document.getElementById("resultado");

document.getElementById("sair").addEventListener("click", sair);

function faltando() {
  if (!senhaAtual.value || !novaSenha.value) return "Preencha a senha atual e a nova senha.";
  if (novaSenha.value !== repetir.value) return "A nova senha e a repetição não são iguais.";
  return null;
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const erro = faltando();
  if (erro) {
    resultado.replaceChildren(mensagem("erro", erro));
    return;
  }
  trocar.disabled = true;
  try {
    await api("PUT", "/eu/senha", { senha_atual: senhaAtual.value, nova_senha: novaSenha.value });
    formulario.reset();
    resultado.replaceChildren(mensagem("sucesso", "Senha trocada. Use a nova senha na próxima vez que entrar."));
  } catch (e) {
    resultado.replaceChildren(mensagem("erro", e.message));
  } finally {
    trocar.disabled = false;
  }
});

const eu = await cabecalho();
if (eu) {
  document.getElementById("usuario").value = eu.email;
  document.getElementById("voce").replaceChildren(
    el("p", { class: "conta-nome" }, el("strong", {}, eu.nome), el("span", { class: "suave" }, eu.email)),
    el("div", { class: "selos" }, selosDePapel(eu.papeis)),
  );
}
