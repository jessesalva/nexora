# NEXORA ROBOT 2.0
# Analise automatica de oportunidades reais da AWIN

import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path


PASTA = Path(__file__).parent

ARQUIVO_FEED = PASTA / "12374-42501-it_IT-Lastminute_IT_DP.csv.gz"
ARQUIVO_SAIDA = PASTA / "nexora_deals.json"


def converter_preco(valor):
    if not valor:
        return None

    texto = str(valor).replace("EUR", "").replace("€", "").strip()

    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def carregar_ofertas():
    ofertas = []

    with gzip.open(
        ARQUIVO_FEED,
        "rt",
        encoding="utf-8-sig",
        errors="replace"
    ) as arquivo:

        leitor = csv.DictReader(arquivo)

        for linha in leitor:

            preco = converter_preco(linha.get("search_price"))

            if preco is None or preco <= 0:
                continue

            preco_original = converter_preco(linha.get("store_price"))

            nome = (linha.get("product_name") or "").strip()

            destino = (
                linha.get("Travel:destination_name")
                or linha.get("Travel:destination_city")
                or linha.get("location")
                or ""
            ).strip()

            oferta = {
                "nome": nome,
                "preco": preco,
                "preco_original": preco_original,
                "moeda": (linha.get("currency") or "EUR").strip(),
                "destino": destino,
                "ida": (linha.get("Travel:departure_date") or "").strip(),
                "volta": (linha.get("Travel:return_date") or "").strip(),
                "imagem": (linha.get("merchant_image_url") or "").strip(),
                "link": (linha.get("aw_deep_link") or "").strip(),
            }

            ofertas.append(oferta)

    return ofertas


def remover_duplicados(ofertas):
    unicas = {}

    for oferta in ofertas:

        chave = (
            oferta["nome"].lower(),
            oferta["ida"],
            oferta["volta"],
            round(oferta["preco"], 2)
        )

        if chave not in unicas:
            unicas[chave] = oferta

    return list(unicas.values())


def calcular_desconto(oferta):
    atual = oferta["preco"]
    original = oferta["preco_original"]

    if not original or original <= atual:
        return 0

    return ((original - atual) / original) * 100


def calcular_scores(ofertas):

    por_destino = defaultdict(list)

    for oferta in ofertas:
        destino = oferta["destino"] or "SEM_DESTINO"
        por_destino[destino].append(oferta)

    for destino, grupo in por_destino.items():

        grupo.sort(key=lambda x: x["preco"])

        total = len(grupo)

        for posicao, oferta in enumerate(grupo):

            # 1. Preco competitivo: ate 45 pontos
            if total == 1:
                pontos_preco = 45
            else:
                percentil = 1 - (posicao / (total - 1))
                pontos_preco = percentil * 45

            # 2. Desconto: ate 35 pontos
            desconto = calcular_desconto(oferta)

            pontos_desconto = min(desconto, 35)

            # 3. Qualidade dos dados: ate 20 pontos
            pontos_dados = 0

            if oferta["destino"]:
                pontos_dados += 4

            if oferta["ida"]:
                pontos_dados += 4

            if oferta["volta"]:
                pontos_dados += 4

            if oferta["imagem"]:
                pontos_dados += 4

            if oferta["link"]:
                pontos_dados += 4

            score = (
                pontos_preco
                + pontos_desconto
                + pontos_dados
            )

            oferta["desconto_percentual"] = round(desconto, 2)
            oferta["nexora_score"] = round(score, 2)

    return ofertas


def classificar_oferta(score):
    if score >= 85:
        return "EXCELENTE"

    if score >= 70:
        return "MUITO BOA"

    if score >= 55:
        return "BOA"

    return "REGULAR"


def selecionar_melhores(ofertas, quantidade=20):

    ordenadas = sorted(
        ofertas,
        key=lambda x: x["nexora_score"],
        reverse=True
    )

    resultado = []
    destinos_usados = {}

    for oferta in ordenadas:

        destino = oferta["destino"]

        quantidade_destino = destinos_usados.get(destino, 0)

        # Evita que um unico destino domine todo o ranking
        if quantidade_destino >= 3:
            continue

        destinos_usados[destino] = quantidade_destino + 1

        resultado.append(oferta)

        if len(resultado) >= quantidade:
            break

    return resultado


def salvar_json(ofertas):

    with open(
        ARQUIVO_SAIDA,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            ofertas,
            arquivo,
            ensure_ascii=False,
            indent=2
        )


def executar():

    print("====================================")
    print("       NEXORA ROBOT 2.0")
    print("====================================")
    print()

    print("Lendo feed real AWIN / lastminute.com...")

    ofertas = carregar_ofertas()

    print(f"Ofertas carregadas: {len(ofertas)}")

    ofertas = remover_duplicados(ofertas)

    print(f"Ofertas apos remover duplicados: {len(ofertas)}")

    ofertas = calcular_scores(ofertas)

    melhores = selecionar_melhores(ofertas)

    salvar_json(melhores)

    print()
    print("========== NEXORA DEALS ==========")

    for posicao, oferta in enumerate(melhores, start=1):

        categoria = classificar_oferta(
            oferta["nexora_score"]
        )

        print()
        print(
            f"{posicao}. "
            f"NEXORA SCORE: {oferta['nexora_score']} "
            f"- {categoria}"
        )

        print(oferta["nome"])

        print(
            f"Preco: "
            f"{oferta['moeda']} "
            f"{oferta['preco']:.2f}"
        )

        if oferta["desconto_percentual"] > 0:
            print(
                f"Economia: "
                f"{oferta['desconto_percentual']}%"
            )

        if oferta["destino"]:
            print(
                f"Destino: {oferta['destino']}"
            )

        if oferta["ida"]:
            print(
                f"Ida: {oferta['ida']}"
            )

        if oferta["volta"]:
            print(
                f"Volta: {oferta['volta']}"
            )

        if oferta["link"]:
            print(
                f"Link afiliado: {oferta['link']}"
            )

    print()
    print("------------------------------------")
    print(
        f"Arquivo criado: {ARQUIVO_SAIDA.name}"
    )
    print("------------------------------------")


if __name__ == "__main__":
    executar()
