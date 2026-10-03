import { api, mensagem, telaInicial } from "./comum.js";

const formulario = document.getElementById("login-form");
const email = document.getElementById("email");
const senha = document.getElementById("senha");
const entrar = document.getElementById("entrar");
const resultado = document.getElementById("resultado");

function volta() {
  const destino = new URLSearchParams(location.search).get("volta");
  if (!destino || !destino.startsWith("/ui/") || destino.includes("login.html")) return null;
  return destino;
}

email.focus();

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!email.value.trim() || !senha.value) {
    resultado.replaceChildren(mensagem("erro", "Preencha o e-mail e a senha."));
    return;
  }
  entrar.disabled = true;
  resultado.replaceChildren();
  try {
    const eu = await api("POST", "/login", { email: email.value.trim(), senha: senha.value });
    const destino = volta() ?? telaInicial(eu);
    if (destino) {
      location.replace(destino);
      return;
    }
    resultado.replaceChildren(mensagem("aviso", "Você entrou, mas o seu papel ainda não tem tela no Copilot. Fale com o admin."));
  } catch (e) {
    senha.value = "";
    senha.focus();
    resultado.replaceChildren(mensagem("erro", e.message));
  }
  entrar.disabled = false;
});
