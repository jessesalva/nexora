# ============================================================
# NEXORA ROBOT 3.3
# Motor inteligente de oportunidades AWIN / lastminute.com
# ============================================================

import csv
import gzip
import json
import re
import statistics

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from datetime import datetime, date

PASTA = Path(__file__).parent

ARQUIVO_FEED = (
    PASTA /
    "12374-42501-it_IT-Lastminute_IT_DP.csv.gz"
)

ARQUIVO_SAIDA = (
    PASTA /
    "nexora_deals.json"
)

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
        return float(
            texto.replace(",", ".")
        )

    except ValueError:
        return None


def normalizar_texto(texto):

    if not texto:
        return ""

    texto = texto.lower().strip()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto


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


def extrair_origem(nome):

    if not nome:
        return ""

    partes = [
        parte.strip()
        for parte in nome.split("-")
        if parte.strip()
    ]

    if not partes:
        return ""

    return partes[0]


def extrair_produto(nome):

    if not nome:
        return ""

    partes = [
        parte.strip()
        for parte in nome.split("-")
        if parte.strip()
    ]

    if not partes:
        return nome.strip()

    return partes[-1]


# ============================================================
# CARREGAR FEED
# ============================================================

def carregar_ofertas():

    ofertas = []

    with gzip.open(
        ARQUIVO_FEED,
        "rt",
        encoding="utf-8-sig",
        errors="replace"
    ) as arquivo:

        leitor = csv.DictReader(
            arquivo
        )

        for linha in leitor:

            preco = converter_preco(
                linha.get("search_price")
            )

            if preco is None:
                continue

            if preco <= 0:
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
                linha.get(
                    "Travel:destination_name"
                )
                or linha.get(
                    "Travel:destination_city"
                )
                or linha.get("location")
                or ""
            ).strip()

            origem = extrair_origem(
                nome
            )

            produto = extrair_produto(
                nome
            )

            oferta = {

                "nome": nome,

                "produto": produto,

                "origem": origem,

                "destino": destino,

                "preco": preco,

                "preco_original":
                    preco_original,

                "moeda": (
                    linha.get("currency")
                    or "EUR"
                ).strip(),

                "ida": (
                    linha.get(
                        "Travel:departure_date"
                    )
                    or ""
                ).strip(),

                "volta": (
                    linha.get(
                        "Travel:return_date"
                    )
                    or ""
                ).strip(),

                "imagem": (
                    linha.get(
                        "merchant_image_url"
                    )
                    or ""
                ).strip(),

                "link": (
                    linha.get(
                        "aw_deep_link"
                    )
                    or ""
                ).strip(),

                "fornecedor":
                    "lastminute.com"
            }

            ofertas.append(
                oferta
            )

    return ofertas


# ============================================================
# REMOVER DUPLICADOS
# ============================================================

def remover_duplicados(ofertas):

    unicas = {}

    for oferta in ofertas:

        chave = (

            normalizar_texto(
                oferta["produto"]
            ),

            normalizar_texto(
                oferta["origem"]
            ),

            normalizar_texto(
                oferta["destino"]
            ),

            oferta["ida"],

            oferta["volta"],

            round(
                oferta["preco"],
                2
            )
        )

        if chave not in unicas:

            unicas[chave] = oferta

    return list(
        unicas.values()
    )


# ============================================================
# DURAÇÃO
# ============================================================

def calcular_duracao(oferta):

    ida = converter_data(
        oferta["ida"]
    )

    volta = converter_data(
        oferta["volta"]
    )

    if not ida or not volta:
        return None

    dias = (
        volta - ida
    ).days

    if dias <= 0:
        return None

    return dias


# ============================================================
# DESCONTO
# ============================================================

def calcular_desconto(oferta):

    atual = oferta["preco"]

    original = oferta[
        "preco_original"
    ]

    if not original:
        return 0

    if original <= atual:
        return 0

    desconto = (
        (original - atual)
        / original
    ) * 100

    if desconto < 0:
        return 0

    if desconto > 90:
        return 0

    return desconto


# ============================================================
# PERCENTIL DE PREÇO
# Quanto menor o preço, maior a nota.
# ============================================================

def calcular_percentil_preco(
    preco,
    precos
):

    if not precos:
        return 0.5

    if len(precos) == 1:
        return 0.5

    menores = sum(
        1
        for valor in precos
        if valor < preco
    )

    percentil = (
        menores /
        (len(precos) - 1)
    )

    resultado = (
        1 - percentil
    )

    return max(
        0,
        min(resultado, 1)
    )


# ============================================================
# DATA
# ============================================================

def calcular_pontos_data(oferta):

    data_ida = converter_data(
        oferta["ida"]
    )

    if not data_ida:
        return 0

    dias = (
        data_ida - date.today()
    ).days

    if dias < 0:
        return -100

    if dias <= 15:
        return 5

    if dias <= 45:
        return 8

    if dias <= 120:
        return 7

    if dias <= 240:
        return 5

    if dias <= 365:
        return 3

    return 1


# ============================================================
# SCORE 3.2
# ============================================================

def calcular_scores(ofertas):

    precos_globais = [
        oferta["preco"]
        for oferta in ofertas
    ]

    precos_por_dia_globais = []

    por_destino = defaultdict(
        list
    )

    por_rota = defaultdict(
        list
    )

    # --------------------------------------------------------
    # Preparar dados
    # --------------------------------------------------------

    for oferta in ofertas:

        duracao = calcular_duracao(
            oferta
        )

        oferta["duracao_dias"] = (
            duracao
        )

        if duracao:

            preco_dia = (
                oferta["preco"]
                / duracao
            )

        else:

            preco_dia = None

        oferta["preco_por_dia"] = (
            round(preco_dia, 2)
            if preco_dia
            else None
        )

        if preco_dia:

            precos_por_dia_globais.append(
                preco_dia
            )

        destino = (
            normalizar_texto(
                oferta["destino"]
            )
            or "sem_destino"
        )

        rota = (

            normalizar_texto(
                oferta["origem"]
            ),

            destino
        )

        por_destino[
            destino
        ].append(
            oferta["preco"]
        )

        por_rota[
            rota
        ].append(
            oferta["preco"]
        )

    # Mediana apenas para diagnóstico
    mediana_global = statistics.median(
        precos_globais
    )

    # --------------------------------------------------------
    # Calcular score individual
    # --------------------------------------------------------

    for oferta in ofertas:

        preco = oferta[
            "preco"
        ]

        destino = (
            normalizar_texto(
                oferta["destino"]
            )
            or "sem_destino"
        )

        rota = (

            normalizar_texto(
                oferta["origem"]
            ),

            destino
        )

        # ====================================================
        # 1. PREÇO GLOBAL
        # Máximo: 20 pontos
        # ====================================================

        percentil_global = (
            calcular_percentil_preco(
                preco,
                precos_globais
            )
        )

        pontos_global = (
            percentil_global * 20
        )

        # ====================================================
        # 2. PREÇO POR DIA
        # Máximo: 20 pontos
        # ====================================================

        preco_dia = oferta[
            "preco_por_dia"
        ]

        if preco_dia:

            percentil_dia = (
                calcular_percentil_preco(
                    preco_dia,
                    precos_por_dia_globais
                )
            )

            pontos_dia = (
                percentil_dia * 20
            )

        else:

            pontos_dia = 0

        # ====================================================
        # 3. COMPETITIVIDADE NO DESTINO
        # Máximo: 15 pontos
        # ====================================================

        grupo_destino = (
            por_destino[
                destino
            ]
        )

        if len(
            grupo_destino
        ) >= 2:

            percentil_destino = (
                calcular_percentil_preco(
                    preco,
                    grupo_destino
                )
            )

            pontos_destino = (
                percentil_destino
                * 15
            )

        else:

            # Não premiamos excessivamente
            # destinos sem comparação.
            pontos_destino = 7.5

        # ====================================================
        # 4. COMPETITIVIDADE NA ROTA
        # Máximo: 10 pontos
        # ====================================================

        grupo_rota = (
            por_rota[
                rota
            ]
        )

        if len(
            grupo_rota
        ) >= 2:

            percentil_rota = (
                calcular_percentil_preco(
                    preco,
                    grupo_rota
                )
            )

            pontos_rota = (
                percentil_rota
                * 10
            )

        else:

            pontos_rota = 5

        # ====================================================
        # 5. DESCONTO REAL
        # Máximo: 12 pontos
        # ====================================================

        desconto = (
            calcular_desconto(
                oferta
            )
        )

        pontos_desconto = min(
            desconto * 0.6,
            12
        )

        # ====================================================
        # 6. QUALIDADE DOS DADOS
        # Máximo: 8 pontos
        # ====================================================

        pontos_dados = 0

        if oferta["destino"]:
            pontos_dados += 1

        if oferta["origem"]:
            pontos_dados += 1

        if oferta["ida"]:
            pontos_dados += 1

        if oferta["volta"]:
            pontos_dados += 1

        if oferta["imagem"]:
            pontos_dados += 2

        if oferta["link"]:
            pontos_dados += 2

        # ====================================================
        # 7. DATA
        # Máximo: 8 pontos
        # ====================================================

        pontos_data = (
            calcular_pontos_data(
                oferta
            )
        )

        # ====================================================
        # 8. DURAÇÃO
        # Máximo: 7 pontos
        # ====================================================

        duracao = oferta[
            "duracao_dias"
        ]

        if duracao is None:

            pontos_duracao = 0

        elif 3 <= duracao <= 5:

            pontos_duracao = 7

        elif duracao == 2:

            pontos_duracao = 6

        elif 6 <= duracao <= 7:

            pontos_duracao = 6

        elif duracao == 1:

            pontos_duracao = 3

        elif 8 <= duracao <= 10:

            pontos_duracao = 4

        else:

            pontos_duracao = 2

        # ====================================================
        # TOTAL
        # ====================================================

        score = (

            pontos_global
            + pontos_dia
            + pontos_destino
            + pontos_rota
            + pontos_desconto
            + pontos_dados
            + pontos_data
            + pontos_duracao
        )

        score = max(
            0,
            min(score, 100)
        )

        oferta[
            "desconto_percentual"
        ] = round(
            desconto,
            2
        )

        oferta[
            "nexora_score"
        ] = round(
            score,
            2
        )

        # Explicação da pontuação
        oferta[
            "score_detalhes"
        ] = {

            "preco_global":
                round(
                    pontos_global,
                    2
                ),

            "preco_por_dia":
                round(
                    pontos_dia,
                    2
                ),

            "destino":
                round(
                    pontos_destino,
                    2
                ),

            "rota":
                round(
                    pontos_rota,
                    2
                ),

            "desconto":
                round(
                    pontos_desconto,
                    2
                ),

            "dados":
                round(
                    pontos_dados,
                    2
                ),

            "data":
                round(
                    pontos_data,
                    2
                ),

            "duracao":
                round(
                    pontos_duracao,
                    2
                )
        }

        oferta[
            "mediana_preco_feed"
        ] = round(
            mediana_global,
            2
        )

    return ofertas


# ============================================================
# CLASSIFICAÇÃO
# ============================================================
def validar_oferta_comercial(oferta):
    """
    Valida se uma oferta possui condicoes minimas
    para ser utilizada comercialmente pela NEXORA.
    """

    motivos = []
    alertas = []

    # ============================================
    # 1. PRECO
    # ============================================

    preco = oferta.get("preco")

    if preco is None or preco <= 0:
        motivos.append("preco_invalido")

    # Preco extremamente baixo pode ser real,
    # mas merece verificacao antes da publicacao.
    elif preco < 10:
        alertas.append("preco_muito_baixo")


    # ============================================
    # 2. ORIGEM E DESTINO
    # ============================================

    origem = (oferta.get("origem") or "").strip()
    destino = (oferta.get("destino") or "").strip()

    if not origem:
        motivos.append("origem_ausente")

    if not destino:
        motivos.append("destino_ausente")

    if (
        origem
        and destino
        and origem.lower() == destino.lower()
    ):
        motivos.append("origem_igual_destino")


    # ============================================
    # 3. DATAS
    # ============================================

    ida_texto = (oferta.get("ida") or "").strip()
    volta_texto = (oferta.get("volta") or "").strip()

    data_ida = None
    data_volta = None

    if not ida_texto or not volta_texto:

        motivos.append("datas_incompletas")

    else:

        try:
            data_ida = datetime.strptime(
                ida_texto,
                "%Y-%m-%d"
            ).date()

            data_volta = datetime.strptime(
                volta_texto,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            motivos.append("datas_invalidas")


    # ============================================
    # 4. VALIDACAO TEMPORAL
    # ============================================

    if data_ida and data_volta:

        hoje = date.today()

        if data_ida < hoje:
            motivos.append("data_ida_passada")

        if data_volta <= data_ida:
            motivos.append("volta_anterior_ou_igual_ida")

        else:

            duracao_calculada = (
                data_volta - data_ida
            ).days

            oferta["duracao_validada"] = (
                duracao_calculada
            )

            # Menos de 1 dia nao faz sentido
            if duracao_calculada < 1:
                motivos.append("duracao_invalida")

            # Viagens acima de 30 dias nao sao
            # rejeitadas, mas recebem alerta
            if duracao_calculada > 30:
                alertas.append("duracao_muito_longa")


    # ============================================
    # 5. PRECO POR DIA
    # ============================================

    preco_dia = oferta.get(
        "preco_por_dia"
    )

    if (
        preco_dia is not None
        and preco_dia <= 0
    ):
        motivos.append("preco_dia_invalido")

    if (
        preco_dia is not None
        and 0 < preco_dia < 5
    ):
        alertas.append(
            "preco_dia_muito_baixo"
        )


    # ============================================
    # 6. LINK DE AFILIADO
    # ============================================

    link = (
        oferta.get("link") or ""
    ).strip()

    if not link:

        motivos.append("link_ausente")

    elif (
        "awin1.com" not in link.lower()
        and "awin.com" not in link.lower()
    ):

        motivos.append(
            "link_afiliado_invalido"
        )


    # ============================================
    # 7. IMAGEM
    # ============================================

    imagem = (
        oferta.get("imagem") or ""
    ).strip()

    # Nao rejeitamos uma boa oferta sem imagem,
    # mas sinalizamos para revisao.
    if not imagem:
        alertas.append("imagem_ausente")


    # ============================================
    # RESULTADO
    # ============================================

    oferta["validacao_comercial"] = {

        "aprovada": len(motivos) == 0,

        "motivos": motivos,

        "alertas": alertas,

        "nivel": (
            "APROVADA"
            if len(motivos) == 0
            and len(alertas) == 0

            else "APROVADA_COM_ALERTA"
            if len(motivos) == 0

            else "REJEITADA"
        )
    }

    return oferta

def calcular_potencial_comercial(oferta):
    """
    Calcula o potencial comercial da oferta.
    Nota independente do NEXORA SCORE.
    """

    pontos = 0
    sinais = []

    preco = oferta.get("preco") or 0
    preco_dia = oferta.get("preco_por_dia")
    duracao = oferta.get("duracao_validada")

    # ============================================
    # 1. PRECO TOTAL - ate 30 pontos
    # ============================================

    if preco <= 100:
        pontos += 30
        sinais.append("preco_muito_atrativo")

    elif preco <= 200:
        pontos += 25
        sinais.append("preco_atrativo")

    elif preco <= 350:
        pontos += 20

    elif preco <= 500:
        pontos += 15

    elif preco <= 750:
        pontos += 10

    else:
        pontos += 5


    # ============================================
    # 2. PRECO POR DIA - ate 30 pontos
    # ============================================

    if preco_dia:

        if preco_dia <= 30:
            pontos += 30
            sinais.append("excelente_preco_dia")

        elif preco_dia <= 50:
            pontos += 25

        elif preco_dia <= 75:
            pontos += 20

        elif preco_dia <= 100:
            pontos += 15

        else:
            pontos += 5


    # ============================================
    # 3. DURACAO - ate 20 pontos
    # ============================================

    if duracao:

        if 3 <= duracao <= 7:
            pontos += 20
            sinais.append("duracao_atrativa")

        elif 2 <= duracao <= 10:
            pontos += 15

        elif duracao <= 14:
            pontos += 10

        else:
            pontos += 5


    # ============================================
    # 4. ANTECEDENCIA - ate 20 pontos
    # ============================================

    ida_texto = oferta.get("ida")

    if ida_texto:

        try:

            data_ida = datetime.strptime(
                ida_texto,
                "%Y-%m-%d"
            ).date()

            dias_ate_viagem = (
                data_ida - date.today()
            ).days

            oferta["dias_ate_viagem"] = dias_ate_viagem

            if 7 <= dias_ate_viagem <= 45:
                pontos += 20
                sinais.append("janela_compra_forte")

            elif 46 <= dias_ate_viagem <= 90:
                pontos += 15

            elif dias_ate_viagem > 90:
                pontos += 10

            elif dias_ate_viagem >= 0:
                pontos += 5

        except ValueError:
            pass


    # ============================================
    # RESULTADO
    # ============================================

    oferta["potencial_comercial"] = round(
        pontos,
        2
    )

    oferta["sinais_comerciais"] = sinais

    return oferta
    
def classificar_oferta(score):

    if score >= 90:
        return "EXCEPCIONAL"

    if score >= 82:
        return "EXCELENTE"

    if score >= 72:
        return "MUITO BOA"

    if score >= 60:
        return "BOA"

    return "REGULAR"


# ============================================================
# SELEÇÃO
# ============================================================

def selecionar_melhores(
    ofertas,
    quantidade=QUANTIDADE_DEALS
):

    # Remove viagens vencidas

    ofertas_validas = []

    for oferta in ofertas:

        data_ida = converter_data(
            oferta["ida"]
        )

        if data_ida:

            if data_ida < date.today():
                continue

        ofertas_validas.append(
            oferta
        )

    ordenadas = sorted(

       ofertas_validas,

       key=lambda x: (
           x.get("potencial_comercial", 0),
           x["nexora_score"],
           -x["preco"]
       ),

       reverse=True
    )

    resultado = []

    produtos_usados = defaultdict(
        int
    )

    destinos_usados = defaultdict(
        int
    )

    origens_usadas = defaultdict(
        int
    )

    rotas_usadas = defaultdict(
        int
    )

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

        rota = (
            origem,
            destino
        )

        # Mesmo hotel/produto
        # no máximo uma vez
        if (
            produto
            and produtos_usados[
                produto
            ] >= 1
        ):
            continue

        # Mesmo destino
        # no máximo 3 vezes
        if (
            destino
            and destinos_usados[
                destino
            ] >= 3
        ):
            continue

        # Mesma rota
        # no máximo 2 vezes
        if (
            rotas_usadas[
                rota
            ] >= 2
        ):
            continue

        # Mesma origem
        # no máximo 7 ofertas
        if (
            origem
            and origens_usadas[
                origem
            ] >= 7
        ):
            continue

        oferta[
            "categoria_score"
        ] = classificar_oferta(
            oferta[
                "nexora_score"
            ]
        )

        resultado.append(
            oferta
        )

        if produto:

            produtos_usados[
                produto
            ] += 1

        if destino:

            destinos_usados[
                destino
            ] += 1

        if origem:

            origens_usadas[
                origem
            ] += 1

        rotas_usadas[
            rota
        ] += 1

        if (
            len(resultado)
            >= quantidade
        ):
            break

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
# EXECUÇÃO
# ============================================================

def executar():

    print()

    print(
        "========================================"
    )

    print(
        "          NEXORA ROBOT 3.4"
    )

    print(
        "========================================"
    )

    print()

    print(
        "Lendo feed REAL AWIN / lastminute.com..."
    )

    ofertas = carregar_ofertas()

    print(
        f"Ofertas carregadas: "
        f"{len(ofertas)}"
    )

    ofertas = remover_duplicados(
        ofertas
    )

    print(
        f"Ofertas apos limpeza: "
        f"{len(ofertas)}"
    )

    ofertas = calcular_scores(
        ofertas
    )

    # ============================================
    # VALIDACAO COMERCIAL
    # ============================================

    ofertas_validadas = []

    aprovadas = 0
    rejeitadas = 0
    motivos_rejeicao = defaultdict(int)

    for oferta in ofertas:

        oferta = validar_oferta_comercial(
            oferta
        )

        if oferta["validacao_comercial"]["aprovada"]:
            aprovadas += 1
            ofertas_validadas.append(
                oferta
            )
        else:
            rejeitadas += 1

            for motivo in oferta["validacao_comercial"]["motivos"]:
                motivos_rejeicao[motivo] += 1

    print()
    print("======= VALIDACAO COMERCIAL =======")
    print(
        f"Ofertas analisadas: {len(ofertas)}"
    )
    print(
        f"Ofertas aprovadas: {aprovadas}"
    )
    print(
        f"Ofertas rejeitadas: {rejeitadas}"
    )
    print()
    print("Motivos das rejeicoes:")

    for motivo, quantidade in sorted(
        motivos_rejeicao.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        print(
            f"- {motivo}: {quantidade}"
        )
    print("===================================")
    print()
    
    # Calcula o potencial comercial
    # de todas as ofertas aprovadas

    for oferta in ofertas:
        calcular_potencial_comercial(
            oferta
        ) 
        
    melhores = selecionar_melhores(
        ofertas_validadas
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
            f"NEXORA "
            f"{oferta['nexora_score']}/100 "
            f"- "
            f"{oferta['categoria_score']}"
        )

        print(
            oferta["nome"]
        )

        print(
            f"Preco: "
            f"{oferta['moeda']} "
            f"{oferta['preco']:.2f}"
        )

        if oferta[
            "preco_por_dia"
        ]:

            print(
                f"Preco/dia: EUR "
                f"{oferta['preco_por_dia']:.2f}"
            )

        if oferta[
            "duracao_dias"
        ]:

            print(
                f"Duracao: "
                f"{oferta['duracao_dias']} dias"
            )

        if oferta[
            "desconto_percentual"
        ] > 0:

            print(
                f"Desconto: "
                f"{oferta['desconto_percentual']}%"
            )

        print(
            f"Origem: "
            f"{oferta['origem']}"
        )

        print(
            f"Destino: "
            f"{oferta['destino']}"
        )

        print(
            f"Ida: "
            f"{oferta['ida']}"
        )

        print(
            f"Volta: "
            f"{oferta['volta']}"
        )

        print()

        print(
            "Composicao do NEXORA SCORE:"
        )

        print(
            f"Potencial comercial: "
            f"{oferta.get('potencial_comercial', 0)}/100"
        )

        sinais = oferta.get(
            "sinais_comerciais",
            []
        )

        if sinais:
            print(
                "Sinais comerciais: "
                + ", ".join(sinais)
            )

        print()

        detalhes = oferta[
            "score_detalhes"
        ]

        print(
            f"  Preco global: "
            f"{detalhes['preco_global']}/20"
        )

        print(
            f"  Preco/dia: "
            f"{detalhes['preco_por_dia']}/20"
        )

        print(
            f"  Destino: "
            f"{detalhes['destino']}/15"
        )

        print(
            f"  Rota: "
            f"{detalhes['rota']}/10"
        )

        print(
            f"  Desconto: "
            f"{detalhes['desconto']}/12"
        )

        print(
            f"  Dados: "
            f"{detalhes['dados']}/8"
        )

        print(
            f"  Data: "
            f"{detalhes['data']}/8"
        )

        print(
            f"  Duracao: "
            f"{detalhes['duracao']}/7"
        )

        if oferta["link"]:

            print(
                f"Link afiliado: "
                f"{oferta['link']}"
            )

        print(
            "------------------------------------"
        )

    print()

    print(
        f"Arquivo criado: "
        f"{ARQUIVO_SAIDA.name}"
    )

    print(
        f"Deals selecionados: "
        f"{len(melhores)}"
    )

    print()

    print(
        "NEXORA Robot 3.2 finalizado."
    )


if __name__ == "__main__":
    executar()
