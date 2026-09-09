"""Testes de core/ia_resumo.py — cobrem só o que é testável sem rede (o
sandbox de CI não deve depender de uma ANTHROPIC_API_KEY de verdade nem
fazer chamada real de API a cada push, mesmo princípio de test_telegram.py
pra api.telegram.org).

O caso mais importante aqui não é "a IA responde direito" (isso não dá pra
garantir em CI) — é "sem chave configurada, gerar_resumo() nunca tenta rede
e nunca lança exceção", porque é essa garantia que permite o resto do
projeto (main.py, notifier/telegram.py) chamar a função sem nenhum guard
extra.
"""

from dataclasses import dataclass

import pytest

import core.ia_resumo as ia_resumo


@dataclass
class _JobFalso:
    """Só os campos que gerar_resumo() lê — não precisa do Job real de
    core/job.py (que tem muitos outros campos obrigatórios sem relação com
    este teste)."""
    titulo: str = "Analista de Master Data Sênior"
    empresa: str = "Empresa Exemplo"
    motivo: str = "Cargo forte + ferramenta SAP"
    descricao: str = ""


def test_sem_chave_devolve_vazio_sem_tentar_rede(monkeypatch):
    """Sem ANTHROPIC_API_KEY, gerar_resumo() deve devolver "" na primeira
    linha — sem sequer tentar importar o SDK. Simula "chave ausente"
    sobrescrevendo o módulo já carregado (a leitura de os.getenv acontece
    uma vez, no import do módulo — refazer isso aqui evita depender de que
    nenhuma ANTHROPIC_API_KEY exista no ambiente de quem roda o teste)."""
    monkeypatch.setattr(ia_resumo, "ANTHROPIC_API_KEY", "")
    resultado = ia_resumo.gerar_resumo(_JobFalso())
    assert resultado == ""


def test_falha_na_chamada_nunca_lanca_excecao(monkeypatch):
    """Com chave presente mas a chamada de API falhando (rede indisponível,
    chave inválida, o que for), gerar_resumo() deve devolver "" — nunca
    propagar a exceção. É essa garantia que permite main.py chamar
    gerar_resumo() sem try/except ao redor."""
    monkeypatch.setattr(ia_resumo, "ANTHROPIC_API_KEY", "chave-forjada-para-teste")

    class _ClienteQuebrado:
        def __init__(self, api_key):
            pass

        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("falha simulada de rede/API")

    class _ModuloAnthropicFalso:
        Anthropic = _ClienteQuebrado

    monkeypatch.setitem(__import__("sys").modules, "anthropic", _ModuloAnthropicFalso())

    resultado = ia_resumo.gerar_resumo(_JobFalso())
    assert resultado == ""


_CASOS_CONTEXTO = [
    ("sem-descricao", "", "Cargo forte + ferramenta SAP"),
    ("com-descricao-curta", "Requisitos: SAP MM, DAMA-DMBOK.", "Requisitos: SAP MM"),
    ("descricao-longa-e-cortada", "x" * 2000, "x" * ia_resumo._LIMITE_CHARS_DESCRICAO),
]


@pytest.mark.parametrize(
    "nome,descricao,esperado_no_contexto",
    _CASOS_CONTEXTO,
    ids=[c[0] for c in _CASOS_CONTEXTO],
)
def test_contexto_inclui_descricao_cortada_no_limite(monkeypatch, nome, descricao, esperado_no_contexto):
    """O texto mandado pro modelo deve incluir a descrição da vaga quando
    existir, mas nunca mais que _LIMITE_CHARS_DESCRICAO caracteres dela —
    resumo de 1-2 frases não precisa da descrição inteira, e isso mantém o
    custo de tokens por chamada previsível (ver comentário no módulo)."""
    monkeypatch.setattr(ia_resumo, "ANTHROPIC_API_KEY", "chave-forjada-para-teste")

    capturado = {}

    class _ClienteEspiao:
        def __init__(self, api_key):
            pass

        class messages:
            @staticmethod
            def create(**kwargs):
                capturado["mensagens"] = kwargs["messages"]

                class _Bloco:
                    type = "text"
                    text = "resumo forjado"

                class _Resposta:
                    content = [_Bloco()]

                return _Resposta()

    class _ModuloAnthropicFalso:
        Anthropic = _ClienteEspiao

    monkeypatch.setitem(__import__("sys").modules, "anthropic", _ModuloAnthropicFalso())

    resultado = ia_resumo.gerar_resumo(_JobFalso(descricao=descricao))

    assert resultado == "resumo forjado"
    conteudo_enviado = capturado["mensagens"][0]["content"]
    assert esperado_no_contexto in conteudo_enviado
    if descricao:
        # Nunca manda mais que o limite, mesmo que a descrição original seja maior.
        assert len(descricao) <= ia_resumo._LIMITE_CHARS_DESCRICAO or (
            descricao[: ia_resumo._LIMITE_CHARS_DESCRICAO] in conteudo_enviado
            and descricao not in conteudo_enviado
        )
