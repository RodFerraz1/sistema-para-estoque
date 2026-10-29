// Leitor de código de barras pela câmera. Usa o BarcodeDetector do navegador (Chrome no
// Android) e, onde ele não existe ou não lê EAN (Safari no iPhone), o ponyfill com a mesma API.
const PONYFILL = "https://cdn.jsdelivr.net/npm/barcode-detector@3.2.2/ponyfill/+esm";
const FORMATOS = ["ean_13", "ean_8"];
const INTERVALO_MS = 150;
// O mesmo código em leituras seguidas, para não aceitar um quadro tremido lido errado.
const LEITURAS_IGUAIS = 2;

const dialogo = document.getElementById("leitor");
const video = document.getElementById("leitor-video");
const status = document.getElementById("leitor-status");
const cameras = document.getElementById("leitor-cameras");
const camera = document.getElementById("leitor-camera");
const foto = document.getElementById("leitor-foto");
const arquivo = document.getElementById("leitor-arquivo");

let detector = null;
let fluxo = null;
let sessao = 0;
let responder = null;

async function criarDetector() {
  if (detector) return detector;
  let Detector = globalThis.BarcodeDetector;
  const nativo = Detector && (await Detector.getSupportedFormats()).includes("ean_13");
  if (!nativo) ({ BarcodeDetector: Detector } = await import(PONYFILL));
  detector = new Detector({ formats: FORMATOS });
  return detector;
}

function pararCamera() {
  sessao++;
  fluxo?.getTracks().forEach((t) => t.stop());
  fluxo = null;
  video.srcObject = null;
}

function terminar(codigo) {
  pararCamera();
  const r = responder;
  responder = null;
  if (dialogo.open) dialogo.close();
  r?.(codigo);
}

function semCamera(texto) {
  status.textContent = texto;
  foto.hidden = false;
}

async function listarCameras(atual) {
  const dispositivos = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  cameras.hidden = dispositivos.length < 2;
  camera.replaceChildren(
    ...dispositivos.map((d, i) => {
      const opcao = document.createElement("option");
      opcao.value = d.deviceId;
      opcao.textContent = d.label || `Câmera ${i + 1}`;
      return opcao;
    }),
  );
  camera.value = atual;
}

async function procurar(minhaSessao, leitor) {
  let ultimo = null;
  let vezes = 0;
  while (minhaSessao === sessao) {
    if (video.readyState >= video.HAVE_CURRENT_DATA) {
      const [achado] = await leitor.detect(video).catch(() => []);
      const codigo = achado?.rawValue ?? null;
      vezes = codigo !== null && codigo === ultimo ? vezes + 1 : 1;
      ultimo = codigo;
      if (codigo !== null && vezes >= LEITURAS_IGUAIS && minhaSessao === sessao) return terminar(codigo);
    }
    await new Promise((r) => setTimeout(r, INTERVALO_MS));
  }
}

async function ligarCamera(deviceId) {
  pararCamera();
  const minhaSessao = sessao;
  status.textContent = "Abrindo a câmera...";
  if (!navigator.mediaDevices?.getUserMedia) {
    return semCamera("O navegador não deixa abrir a câmera por aqui. Tire uma foto do código ou digite os números.");
  }
  try {
    const [leitor, novo] = await Promise.all([
      criarDetector(),
      navigator.mediaDevices.getUserMedia({
        video: {
          ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: { ideal: "environment" } }),
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      }),
    ]);
    if (minhaSessao !== sessao) return novo.getTracks().forEach((t) => t.stop());
    fluxo = novo;
    video.srcObject = fluxo;
    await video.play();
    status.textContent = "Segure o celular parado, com o código dentro do quadro.";
    listarCameras(fluxo.getVideoTracks()[0].getSettings().deviceId).catch(() => {});
    procurar(minhaSessao, leitor);
  } catch (e) {
    if (minhaSessao !== sessao) return;
    if (e.name === "NotAllowedError") semCamera("Sem permissão para usar a câmera. Libere nas configurações do navegador ou tire uma foto do código.");
    else if (e.name === "NotFoundError" || e.name === "OverconstrainedError") semCamera("Nenhuma câmera encontrada. Tire uma foto do código ou digite os números.");
    else if (e.name === "NotReadableError") semCamera("A câmera está aberta em outro aplicativo. Feche o outro aplicativo ou tire uma foto do código.");
    else semCamera("Não foi possível abrir o leitor. Digite os números do código de barras.");
  }
}

camera.addEventListener("change", () => ligarCamera(camera.value));

arquivo.addEventListener("change", async () => {
  const [imagem] = arquivo.files;
  arquivo.value = "";
  if (!imagem) return;
  status.textContent = "Lendo a foto...";
  try {
    const [achado] = await (await criarDetector()).detect(await createImageBitmap(imagem));
    if (achado) return terminar(achado.rawValue);
    status.textContent = "Não achamos um código de barras na foto. Tente de novo, mais perto e sem reflexo.";
  } catch {
    status.textContent = "Não foi possível ler a foto. Digite os números do código de barras.";
  }
});

dialogo.addEventListener("close", () => terminar(null));

// O código lido, ou null quando a vendedora fecha o leitor sem ler.
export function lerCodigoDeBarras() {
  foto.hidden = true;
  cameras.hidden = true;
  dialogo.showModal();
  ligarCamera(null);
  return new Promise((resolve) => {
    responder = resolve;
  });
}
