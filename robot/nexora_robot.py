# NEXORA ROBOT 3.1
# Analise inteligente de oportunidades reais da AWIN

import csv
import gzip
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


PASTA = Path(__file__).parent

ARQUIVO_FEED = PASTA / "12374-42501-it_IT-Lastminute_IT_DP.csv.gz"
ARQUIVO_SAIDA = PASTA / "nexora_deals.json"

QUANTIDADE_DEALS = 20


# ============================================================
# UTILIDADES
# ============================================================

def converter_preco(valor):
    if not valor:
        return None

    texto = (
        str(valor)
        .replace("EUR", "")
        .replace("€", "")
        .strip()
    )

    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def normalizar_texto(texto):
    if not texto:
        return ""

    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)

    return texto


def extrair_origem(nome):
    if not nome:
        return ""

    partes = [
        p.strip()
        for p in nome.split("-")
        if p.strip()
    ]

    return partes[0] if partes else ""


def extrair_produto(nome):
    if not nome:
        return ""

    partes = [
        p.strip()
        for p in nome.split("-")
        if p.strip()
    ]

    return partes[-1] if partes else nome.strip()


def converter_data(valor):
    if not valor:
        return None

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(
                valor,
                formato
            ).date()
        except ValueError:
            pass

    return None


# ============================================================
# LEITURA DO FEED
# ============================================================

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

            preco = converter_preco(
                linha.get("search_price")
            )

            if preco is None or preco <= 0:
                continue

            preco_original = converter_preco(
                linha.get("store_price")
            )

            nome = (
                linha.get("product_name")
                or ""
            ).strip()

            if not nome:
                continue

            destino = (
                linha.get("Travel:destination_name")
                or linha.get("Travel:destination_city")
                or linha.get("location")
                or ""
            ).strip()

            origem = extrair_origem(nome)
            produto = extrair_produto(nome)

            oferta = {
                "nome": nome,
                "produto": produto,
                "origem": origem,
                "preco": preco,
                "preco_original": preco_original,
                "moeda": (
                    linha.get("currency")
                    or "EUR"
                ).strip(),
                "destino": destino,
                "ida": (
                    linha.get("Travel:departure_date")
                    or ""
                ).strip(),
                "volta": (
                    linha.get("Travel:return_date")
                    or ""
                ).strip(),
                "imagem": (
                    linha.get("merchant_image_url")
                    or ""
                ).strip(),
                "link": (
                    linha.get("aw_deep_link")
                    or ""
                ).strip(),
                "fornecedor": "lastminute.com",
            }

            ofertas.append(oferta)

    return ofertas


# ============================================================
# DUPLICADOS
# ============================================================

def remover_duplicados(ofertas):
    unicas = {}

    for oferta in ofertas:

        chave = (
            normalizar_texto(oferta["produto"]),
            normalizar_texto(oferta["origem"]),
            normalizar_texto(oferta["destino"]),
            oferta["ida"],
            oferta["volta"],
            round(oferta["preco"], 2),
        )

        if chave not in unicas:
            unicas[chave] = oferta

    return list(unicas.values())


# ============================================================
# DESCONTO
# ============================================================

def calcular_desconto(oferta):
    atual = oferta["preco"]
    original = oferta["preco_original"]

    if not original:
        return 0

    if original <= atual:
        return 0

    desconto = (
        (original - atual)
        / original
    ) * 100

    if desconto < 0 or desconto > 90:
        return 0

    return desconto


# ============================================================
# DURAÇÃO
# ============================================================

def calcular_duracao(oferta):
    ida = converter_data(oferta["ida"])
    volta = converter_data(oferta["volta"])

    if not ida or not volta:
        return None

    dias = (volta - ida).days

    if dias <= 0:
        return None

    return dias


# ============================================================
# SCORE DE DATA
# ============================================================

def calcular_pontos_data(oferta):
    data_ida = converter_data(
        oferta["ida"]
    )

    if not data_ida:
        return 0

    hoje = date.today()

    dias = (
        data_ida - hoje
    ).days

    if dias < 0:
        return -100

    if dias <= 15:
        return 7

    if dias <= 60:
        return 10

    if dias <= 120:
        return 8

    if dias <= 240:
        return 6

    if dias <= 365:
        return 4

    return 2


# ============================================================
# SCORE PRINCIPAL
# ============================================================

def calcular_scores(ofertas):

    por_destino = defaultdict(list)
    por_rota = defaultdict(list)

    for oferta in ofertas:

        destino = (
            normalizar_texto(oferta["destino"])
            or "sem_destino"
        )

        rota = (
            normalizar_texto(oferta["origem"]),
            destino,
        )

        por_destino[destino].append(oferta)
        por_rota[rota].append(oferta)

    for oferta in ofertas:

        destino = (
            normalizar_texto(oferta["destino"])
            or "sem_destino"
        )

        rota = (
            normalizar_texto(oferta["origem"]),
            destino,
        )

        grupo_destino = sorted(
            por_destino[destino],
            key=lambda x: x["preco"]
        )

        grupo_rota = sorted(
            por_rota[rota],
            key=lambda x: x["preco"]
        )

        # ====================================================
        # 1. PREÇO NO DESTINO - ATÉ 25
        # ====================================================

        total_destino = len(
            grupo_destino
        )

        posicao_destino = grupo_destino.index(
            oferta
        )

        if total_destino <= 1:
            pontos_preco_destino = 18
        else:
            percentil = (
                1
                - (
                    posicao_destino
                    / (total_destino - 1)
                )
            )

            pontos_preco_destino = (
                percentil * 25
            )

        # ====================================================
        # 2. PREÇO NA ROTA - ATÉ 20
        # ====================================================

        total_rota = len(
            grupo_rota
        )

        posicao_rota = grupo_rota.index(
            oferta
        )

        if total_rota <= 1:
            pontos_preco_rota = 12
        else:
            percentil_rota = (
                1
                - (
                    posicao_rota
                    / (total_rota - 1)
                )
            )

            pontos_preco_rota = (
                percentil_rota * 20
            )

        # ====================================================
        # 3. DESCONTO REAL - ATÉ 20
        # ====================================================

        desconto = calcular_desconto(
            oferta
        )

        pontos_desconto = min(
            desconto,
            20
        )

        # ====================================================
        # 4. QUALIDADE DOS DADOS - ATÉ 15
        # ====================================================

        pontos_dados = 0

        if oferta["destino"]:
            pontos_dados += 3

        if oferta["ida"]:
            pontos_dados += 3

        if oferta["volta"]:
            pontos_dados += 3

        if oferta["imagem"]:
            pontos_dados += 3

        if oferta["link"]:
            pontos_dados += 3

        # ====================================================
        # 5. DATA - ATÉ 10
        # ====================================================

        pontos_data = calcular_pontos_data(
            oferta
        )

        # ====================================================
        # 6. DURAÇÃO - ATÉ 10
        # ====================================================

        duracao = calcular_duracao(
            oferta
        )

        if duracao is None:
            pontos_duracao = 0

        elif 2 <= duracao <= 4:
            pontos_duracao = 10

        elif 5 <= duracao <= 7:
            pontos_duracao = 8

        elif duracao == 1:
            pontos_duracao = 5

        elif 8 <= duracao <= 10:
            pontos_duracao = 5

        else:
            pontos_duracao = 3

        # ====================================================
        # SCORE TOTAL
        # ====================================================

        score = (
            pontos_preco_destino
            + pontos_preco_rota
            + pontos_desconto
            + pontos_dados
            + pontos_data
            + pontos_duracao
        )

        score = min(
            max(score, 0),
            100
        )

        oferta["duracao_dias"] = duracao

        oferta["desconto_percentual"] = round(
            desconto,
            2
        )

        oferta["nexora_score"] = round(
            score,
            2
        )

    return ofertas


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def classificar_oferta(score):

    if score >= 85:
        return "EXCELENTE"

    if score >= 70:
        return "MUITO BOA"

    if score >= 55:
        return "BOA"

    return "REGULAR"


# ============================================================
# SELEÇÃO FINAL
# ============================================================

def selecionar_melhores(
    ofertas,
    quantidade=QUANTIDADE_DEALS
):

    ordenadas = sorted(
        ofertas,
        key=lambda x: x["nexora_score"],
        reverse=True
    )

    resultado = []

    produtos_usados = defaultdict(int)
    destinos_usados = defaultdict(int)
    rotas_usadas = defaultdict(int)

    for oferta in ordenadas:

        produto = normalizar_texto(
            oferta["produto"]
        )

        destino = normalizar_texto(
            oferta["destino"]
        )

        rota = (
            normalizar_texto(
                oferta["origem"]
            ),
            destino,
        )

        # Mesmo hotel/produto apenas uma vez
        if produto and produtos_usados[produto] >= 1:
            continue

        # Mesmo destino no máximo 3 vezes
        if destino and destinos_usados[destino] >= 3:
            continue

        # Mesma rota no máximo 2 vezes
        if rotas_usadas[rota] >= 2:
            continue

        oferta["categoria_score"] = (
            classificar_oferta(
                oferta["nexora_score"]
            )
        )

        resultado.append(
            oferta
        )

        if produto:
            produtos_usados[produto] += 1

        if destino:
            destinos_usados[destino] += 1

        rotas_usadas[rota] += 1

        if len(resultado) >= quantidade:
            break

    return resultado


# ============================================================
# JSON
# ============================================================

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


# ============================================================
# EXECUÇÃO
# ============================================================

def executar():

    print()
    print("====================================")
    print("       NEXORA ROBOT 3.1")
    print("====================================")
    print()

    print(
        "Lendo feed REAL AWIN / lastminute.com..."
    )

    ofertas = carregar_ofertas()

    print(
        f"Ofertas carregadas: {len(ofertas)}"
    )

    ofertas = remover_duplicados(
        ofertas
    )

    print(
        f"Ofertas apos limpeza: {len(ofertas)}"
    )

    ofertas = calcular_scores(
        ofertas
    )

    melhores = selecionar_melhores(
        ofertas
    )

    salvar_json(
        melhores
    )

    print()
    print(
        "========== NEXORA DEALS =========="
    )

    for posicao, oferta in enumerate(
        melhores,
        start=1
    ):

        print()

        print(
            f"{posicao}. "
            f"NEXORA {oferta['nexora_score']}/100 "
            f"- {oferta['categoria_score']}"
        )

        print(
            oferta["nome"]
        )

        print(
            f"Preco: "
            f"{oferta['moeda']} "
            f"{oferta['preco']:.2f}"
        )

        if oferta["desconto_percentual"] > 0:
            print(
                "Economia: "
                f"{oferta['desconto_percentual']}%"
            )

        if oferta["duracao_dias"]:
            print(
                f"Duracao: "
                f"{oferta['duracao_dias']} dias"
            )

        if oferta["origem"]:
            print(
                f"Origem: {oferta['origem']}"
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
    print(
        "------------------------------------"
    )

    print(
        f"Arquivo criado: "
        f"{ARQUIVO_SAIDA.name}"
    )

    print(
        f"Deals selecionados: "
        f"{len(melhores)}"
    )

    print(
        "------------------------------------"
    )


if __name__ == "__main__":
    executar()
