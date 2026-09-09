"""Testes do caminho do banco (DB_PATH).

MEDIDO: o commit b8227b0 moveu core/config.py da raiz pra core/ e, como
DB_PATH era relativo a __file__, o banco se mudou junto sem ninguem
perceber - data/jobs.db (1.080 vagas) ficou orfao e o programa passou a
usar um core/data/jobs.db vazio. Nenhum dos 76 testes existentes cobria o
caminho do banco, entao o CI continuou verde com o sistema sem memoria.

Estes testes existem pra que uma reorganizacao futura de pastas quebre o
teste, nao a producao.
"""

import importlib
import os

import core.config


def _recarregar_config():
    """DB_PATH e calculado no import do modulo - pra testar o efeito de uma
    variavel de ambiente, o modulo precisa ser reimportado."""
    return importlib.reload(core.config)


def test_db_path_aponta_pra_data_na_raiz_do_projeto(monkeypatch):
    monkeypatch.delenv("JOBRADAR_DB_PATH", raising=False)
    config = _recarregar_config()

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(core.config.__file__)))
    assert config.DB_PATH == os.path.join(raiz, "data", "jobs.db")


def test_db_path_nao_fica_dentro_de_core(monkeypatch):
    """A regressao concreta que aconteceu: core/data/jobs.db em vez de
    data/jobs.db."""
    monkeypatch.delenv("JOBRADAR_DB_PATH", raising=False)
    config = _recarregar_config()

    pasta_do_config = os.path.dirname(os.path.abspath(core.config.__file__))
    assert not config.DB_PATH.startswith(os.path.join(pasta_do_config, ""))


def test_db_path_respeita_variavel_de_ambiente(monkeypatch, tmp_path):
    """Permite apontar um banco descartavel em teste sem escrever no real."""
    alvo = str(tmp_path / "jobs_de_teste.db")
    monkeypatch.setenv("JOBRADAR_DB_PATH", alvo)
    config = _recarregar_config()

    assert config.DB_PATH == alvo


def test_database_usa_o_mesmo_db_path_do_config(monkeypatch):
    """database.py importa DB_PATH de core.config - se um dia passar a
    calcular caminho por conta propria, os dois divergem em silencio."""
    monkeypatch.delenv("JOBRADAR_DB_PATH", raising=False)
    config = _recarregar_config()
    import database.database as db
    importlib.reload(db)

    assert db.DB_PATH == config.DB_PATH
