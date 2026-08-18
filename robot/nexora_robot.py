# NEXORA ROBOT
# Motor inicial de análise de oportunidades

from dataclasses import dataclass


@dataclass
class Produto:
    nome: str
    preco: float
    desconto: float
    avaliacao: float
    numero_avaliacoes: int
    comissao: float


def calcular_nexora_score(produto):
    score = 0

    # Desconto
    score += min(produto.desconto * 1.5, 30)

    # Avaliação
    score += (produto.avaliacao / 5) * 25

    # Popularidade
    score += min(produto.numero_avaliacoes / 100, 20)

    # Comissão
    score += min(produto.comissao * 2.5, 25)

    return round(score, 2)


print("NEXORA ROBOT iniciado com sucesso!")
