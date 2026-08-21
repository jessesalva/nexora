# NEXORA ROBOT 3.0
# Motor inteligente de selecao de oportunidades reais da AWIN

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
# CONVERSAO E NORMALIZACAO
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
    """
    Tenta descobrir a cidade de origem usando
    a primeira parte do nome da oferta.
    Exemplo:
    Milano - Palermo - Hotel X
    retorna Milano
    """

    if not nome:
        return ""

    partes = [
        parte.strip()
        for parte in nome.split("-")
        if parte.strip()
    ]

    if partes:
        return partes[0]

    return ""


def extrair_produto(nome):
    """
    Tenta identificar hotel/produto principal.
    Normalmente a ultima parte do nome da AWIN.
    """

    if not nome:
        return ""

    partes = [
        parte.strip()
        for parte in nome.split("-")
        if parte.strip()
    ]

    if partes:
        return partes[-1]

    return nome.strip()


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
# LIMPEZA DE DUPLICADOS
# ============================================================

def remover_duplicados(ofertas):
    unicas = {}

    for oferta in ofertas:

        chave = (
            normalizar_texto(oferta["produto"]),
            normalizar_texto(oferta["origem"]),
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
# DATAS
# ============================================================

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


def calcular_pontos_data(oferta):
    """
    Ate 10 pontos.
    Favorece viagens futuras e relativamente proximas.
    """

    data_ida = converter_data(
        oferta["ida"]
    )

    if not data_ida:
        return 0

    hoje = date.today()

    dias = (data_ida - hoje).days

    # Oferta vencida
    if dias < 0:
        return -50

    # Muito proxima
    if dias <= 7:
        return 7

    # Excelente janela comercial
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
# SCORE DE PRECO
# ============================================================

def calcular_scores(ofertas):

    por_destino = defaultdict(list)

    for oferta in ofertas:

        destino = (
            normalizar_texto(oferta["destino"])
            or "sem_destino"
        )

        por_destino[destino].append(oferta)

    for destino, grupo in por_destino.items():

        grupo.sort(
            key=lambda x: x["preco"]
        )

        total = len(grupo)

        for posicao, oferta in enumerate(grupo):

            # ------------------------------------
            # 1. PRECO COMPETITIVO
            # Ate 35 pontos
            # ------------------------------------

            if total == 1:
                pontos_preco = 25
            else:
                percentil = (
                    1
                    - (
                        posicao
                        / (total - 1)
                    )
                )

                pontos_preco = (
                    percentil * 35
                )

            # ------------------------------------
            # 2. DESCONTO REAL
            # Ate 25 pontos
            # ------------------------------------

            desconto = calcular_desconto(
                oferta
            )

            pontos_desconto = min(
                desconto,
                25
            )

            # ------------------------------------
            # 3. QUALIDADE DOS DADOS
            # Ate 15 pontos
            # ------------------------------------

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

            # ------------------------------------
            # 4. DATA / URGENCIA
            # Ate 10 pontos
            # ------------------------------------

            pontos_data = calcular_pontos_data(
                oferta
            )

            # ------------------------------------
            # SCORE BASE
            # Maximo inicial = 85
            # Os 15 restantes serao usados
            # na diversidade.
            # ------------------------------------

            score_base = (
                pontos_preco
                + pontos_desconto
                + pontos_dados
                + pontos_data
            )

            oferta["desconto_percentual"] = round(
                desconto,
                2
            )

            oferta["score_base"] = round(
                score_base,
                2
            )

    return ofertas


# ============================================================
# CLASSIFICACAO
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
# SELECAO INTELIGENTE
# ============================================================

def selecionar_melhores(
    ofertas,
    quantidade=QUANTIDADE_DEALS
):

    ordenadas = sorted(
        ofertas,
        key=lambda x: x["score_base"],
        reverse=True
    )

    resultado = []

    produtos_usados = defaultdict(int)
    destinos_usados = defaultdict(int)
    origens_usadas = defaultdict(int)

    for oferta in ordenadas:

        produto = normalizar_texto(
            oferta["produto"]
        )

        destino = normalizar_texto(
            oferta["destino"]
        )

        origem = normalizar_texto(
            oferta["origem"]
        )

        # Evita repeticao excessiva
        # do mesmo hotel/produto
        if produto and produtos_usados[produto] >= 1:
            continue

        # Maximo de 3 ofertas
        # do mesmo destino
        if destino and destinos_usados[destino] >= 3:
            continue

        # Diversidade recebe ate 15 pontos
        pontos_diversidade = 15

        if destino and destinos_usados[destino] > 0:
            pontos_diversidade -= 5

        if origem and origens_usadas[origem] >= 3:
            pontos_diversidade -= 3

        score_final = (
            oferta["score_base"]
            + max(pontos_diversidade, 0)
        )

        score_final = min(
            max(score_final, 0),
            100
        )

        oferta["nexora_score"] = round(
            score_final,
            2
        )

        oferta["categoria_score"] = (
            classificar_oferta(
                oferta["nexora_score"]
            )
        )

        resultado.append(oferta)

        if produto:
            produtos_usados[produto] += 1

        if destino:
            destinos_usados[destino] += 1

        if origem:
            origens_usadas[origem] += 1

        if len(resultado) >= quantidade:
            break

    # Ordena novamente pelo score final
    resultado.sort(
        key=lambda x: x["nexora_score"],
        reverse=True
    )

    return resultado


# ============================================================
# SALVAR JSON
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
# EXECUCAO
# ============================================================

def executar():

    print()
    print("====================================")
    print("       NEXORA ROBOT 3.0")
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
        "Ofertas apos limpeza: "
        f"{len(ofertas)}"
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
