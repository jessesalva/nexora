# NEXORA ROBOT
# Leitor inicial de ofertas reais da AWIN

import csv
import gzip
from pathlib import Path


ARQUIVO_FEED = Path(__file__).parent / "12374-42501-it_IT-Lastminute_IT_DP.csv.gz"


def converter_preco(valor):
    if not valor:
        return None

    try:
        return float(
            str(valor)
            .replace("€", "")
            .replace("EUR", "")
            .replace(",", ".")
            .strip()
        )
    except ValueError:
        return None


def carregar_ofertas():
    ofertas = []

    with gzip.open(ARQUIVO_FEED, "rt", encoding="utf-8-sig", errors="replace") as arquivo:
        leitor = csv.DictReader(arquivo)

        for linha in leitor:
            preco = converter_preco(linha.get("search_price"))

            if preco is None or preco <= 0:
                continue

            oferta = {
                "nome": linha.get("product_name", "").strip(),
                "preco": preco,
                "moeda": linha.get("currency", "EUR").strip(),
                "destino": (
                    linha.get("Travel:destination_name")
                    or linha.get("Travel:destination_city")
                    or linha.get("location")
                    or ""
                ).strip(),
                "ida": (linha.get("Travel:departure_date") or "").strip(),
                "volta": (linha.get("Travel:return_date") or "").strip(),
                "imagem": (linha.get("merchant_image_url") or "").strip(),
                "link": (linha.get("aw_deep_link") or "").strip(),
            }

            ofertas.append(oferta)

    return ofertas


def selecionar_melhores_ofertas(ofertas, quantidade=10):
    return sorted(ofertas, key=lambda x: x["preco"])[:quantidade]


def executar():
    print("NEXORA ROBOT iniciado com sucesso!")
    print("Lendo feed REAL da AWIN / lastminute.com...")
    print()

    ofertas = carregar_ofertas()

    print(f"Ofertas válidas encontradas: {len(ofertas)}")
    print()
    print("----- NEXORA DEALS -----")

    melhores = selecionar_melhores_ofertas(ofertas)

    for posicao, oferta in enumerate(melhores, start=1):
        print()
        print(f"{posicao}. {oferta['nome']}")
        print(f"   Preço: {oferta['moeda']} {oferta['preco']:.2f}")

        if oferta["destino"]:
            print(f"   Destino: {oferta['destino']}")

        if oferta["ida"]:
            print(f"   Ida: {oferta['ida']}")

        if oferta["volta"]:
            print(f"   Volta: {oferta['volta']}")

        if oferta["link"]:
            print(f"   Link afiliado: {oferta['link']}")


if __name__ == "__main__":
    executar()
