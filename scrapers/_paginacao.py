"""Forma compartilhada de interpretar um timeout de página entre scrapers
que paginam por tentativa e erro (Gupy, Sólides, 99Jobs).

Ticket 02 de .scratch/melhorias-arquitetura/issues/ (relatório de
arquitetura): os três scrapers reinventavam separadamente a mesma decisão
— "esse timeout significa busca vazia, fim natural da paginação, ou falha
de verdade?" — cada um com seu próprio texto/regex de detecção mas a
MESMA forma de decisão e o MESMO tratamento posterior (log + continue /
log + break / log de aviso + break). Este módulo concentra a forma; o
detector de cada site continua local a cada scraper.
"""

from enum import Enum


class ResultadoPagina(str, Enum):
    """Herda de str de propósito: os scrapers que já comparavam o retorno
    de classificar_timeout contra os literais "vazio"/"fim"/"falha" (nos
    testes existentes de paginação) continuam funcionando sem alteração —
    ResultadoPagina.VAZIO == "vazio" é True com essa herança."""

    VAZIO = "vazio"
    FIM = "fim"
    FALHA = "falha"


def interpretar_timeout(
    *,
    pagina_esta_vazia: bool,
    pagina: int,
) -> ResultadoPagina:
    """Decide o que um timeout significa, dado se o texto da página indica
    "busca vazia" (via o predicado/detector específico do site, já
    avaliado pelo chamador) e em que página o timeout ocorreu.

    - `pagina_esta_vazia=True` na página 1: busca genuinamente sem
      resultado -> VAZIO.
    - `pagina_esta_vazia=True` além da página 1: a paginação natural
      acabou (a página anterior já era a última) -> FIM.
    - `pagina_esta_vazia=False`: a página não carregou de verdade, não é
      fim nem busca vazia -> FALHA.

    Scrapers que não paginam (uma página só, ex.: 99Jobs) sempre chamam
    isto com `pagina=1` — não há como cair no ramo FIM nesse caso, o que é
    o comportamento certo: sem paginação, não existe "fim de paginação"
    para distinguir de "busca vazia"."""
    if pagina_esta_vazia:
        return ResultadoPagina.VAZIO if pagina == 1 else ResultadoPagina.FIM
    return ResultadoPagina.FALHA
