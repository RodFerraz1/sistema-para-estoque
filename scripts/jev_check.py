from typesafe_sdk import Choice, Noul, TypeSafeClient

from src.db.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.jev_key:
        raise SystemExit("JEV_KEY vazio no .env")

    client = TypeSafeClient(api_key=settings.jev_key, model=settings.jev_model)
    response = client.system_one(
        state="Qual a situação do SKU TBC-BEG-70140? Tô com medo de faltar antes do Natal.",
        questions={
            "intencao": Choice(
                instructions="Qual é a intenção do comprador",
                criteria={
                    "situacao_sku": "Quer saber estoque, giro ou cobertura de um SKU",
                    "sugestao_compra": "Quer saber se deve comprar e quanto",
                    "politica_ou_fornecedor": "Pergunta sobre política de compras ou fornecedor",
                    "fora_de_escopo": "Nada a ver com compras",
                },
            ),
            "urgente": Noul(instructions="O comprador demonstra urgência"),
        },
    )
    print(f"modelo: {response.model}")
    for nome, answer in response.answers.items():
        print(f"{nome}: {answer}")


if __name__ == "__main__":
    main()
