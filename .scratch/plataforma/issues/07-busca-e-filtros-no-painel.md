# 07: Busca e filtros no painel

**What to build:** o comprador chefe acha qualquer SKU no painel enquanto digita (código, nome, cor, tamanho, sem acento nem maiúscula) e filtra por categoria, por motivo e por fornecedor. Cada grupo mostra quantos SKUs tem com o filtro aplicado, e os filtros ficam na URL para mandar o link.

**Blocked by:** 06

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Escala: leitura em lote e filtros")

- [x] `GET /painel?busca=&categoria=&motivo=&fornecedor=`, com a regra de busca do `catalog.buscar_skus` e as contagens por grupo.
- [x] `GET /categorias` com as categorias com SKU ativo.
- [x] Barra de busca e filtros no topo do painel, com debounce, os filtros na query string e um "limpar filtros". Mensagem própria para "nenhum SKU com esses filtros", diferente de "nada pedindo atenção".
- [x] Testes HTTP para cada filtro, para a combinação deles e para as contagens. O teste de UI cobre as rotas novas.
- [x] Verificado no navegador, no desktop e no celular. Typecheck e suíte completa verdes.

## Comments

**2026-10-04 (agente):** `GET /painel?busca=&categoria=&motivo=&fornecedor=` filtra sobre o mesmo retrato em lote (as 9 consultas não mudam). A regra de busca saiu do `catalog` como `palavras_da_busca`/`sku_contem_todas` (o `buscar_skus` usa as mesmas). `FiltroPainel` em `painel.schemas`; `ItemAlerta.grupo` (`pedidos_de_vendas | em_ruptura | vao_faltar | outros_alertas`, a mesma regra que ordenava o painel) e `PainelDeAlertas.contagens` vão na resposta (`grupo` em cada item e `contagens` com zero nos grupos vazios); a UI parou de calcular o grupo. Rotas novas em `src/api/catalogo.py`, só do comprador: `GET /categorias` (categorias com SKU ativo) e `GET /fornecedores` (id e nome dos fornecedores que vendem algum SKU ativo, saído do `fornecedores_por_sku`, sem método novo na porta do ERP). Decisões: o filtro `fornecedor` é o id de qualquer fornecedor que vende o SKU, não só o sugerido; `motivo` aceita os valores de `MotivoAlerta` mais `aviso` (aviso aberto) e filtra pelo motivo do SKU, não pelo grupo (um SKU em ruptura com aviso aparece com `motivo=abaixo_do_piso_alerta`, no grupo dos avisos); busca, categoria e fornecedor também filtram os decididos, o motivo não; `skus_com_erro` não é filtrado. `/fornecedores` não está no texto do ticket, mas o select de fornecedor precisa dele (o protótipo não tem esse filtro). UI: barra de filtros no topo do painel (busca com debounce de 300 ms, selects de categoria, motivo e fornecedor, "Limpar filtros" só com filtro ativo), filtros na query string com `history.replaceState`, "Nenhum SKU com esses filtros" separado de "Tudo em dia", `nomeDaCategoria` em `comum.js` (o ticket 08 pode reusar). O select de motivo mostra "Aviso da equipe de vendas" e os motivos da política (os tickets 09 e 12 só precisam pôr o rótulo do motivo novo em `MOTIVOS`). No celular, a barra fica em duas colunas e o resumo também. `cenario_painel.py` ganhou a Katrina (vende `ZERADO` e `MAIS_URGENTE`, mais cara), o `SEM_FORNECEDOR` virou `cama` e o `INATIVO` virou `mesa`. Suíte com 943 testes verde; pyright com os mesmos 79 erros por arquivo.

