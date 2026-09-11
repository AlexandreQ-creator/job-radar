"""Testes de scrapers.gupy._montar_job, sem Playwright.

card_data() representa os campos já extraídos do DOM pela navegação
(scrapers/gupy.py::_buscar_termo) — separando a extração (que precisa de
browser) da montagem do Job (que não precisa), a mesma separação já usada
em scrapers/senior.py::montar_job e scrapers/simplify.py::_montar_job."""

from scrapers.gupy import _montar_job


def card_data(**overrides) -> dict:
    base = {
        "titulo": "Analista de Dados Pleno",
        "empresa": "Empresa Teste",
        "local": "São Paulo, SP",
        "link": "https://portal.gupy.io/job/abc123",
        "publicado_em": "2026-09-01",
        "modalidade": "Híbrido",
    }
    base.update(overrides)
    return base


def test_monta_job_com_todos_os_campos():
    job = _montar_job(card_data())
    assert job.titulo == "Analista de Dados Pleno"
    assert job.empresa == "Empresa Teste"
    assert job.local == "São Paulo, SP"
    assert job.link == "https://portal.gupy.io/job/abc123"
    assert job.site == "Gupy"
    assert job.publicado_em == "2026-09-01"
    assert job.modalidade == "Híbrido"


def test_sem_titulo_devolve_none():
    assert _montar_job(card_data(titulo="")) is None


def test_sem_link_devolve_none():
    assert _montar_job(card_data(link=None)) is None


def test_empresa_ausente_vira_nao_informado():
    job = _montar_job(card_data(empresa=""))
    assert job.empresa == "Não informado"


def test_local_ausente_vira_nao_informado():
    job = _montar_job(card_data(local=""))
    assert job.local == "Não informado"


def test_modalidade_ausente_fica_vazia():
    job = _montar_job(card_data(modalidade=""))
    assert job.modalidade == ""


def test_titulo_com_espacos_e_normalizado():
    job = _montar_job(card_data(titulo="  Analista de Dados  "))
    assert job.titulo == "Analista de Dados"
