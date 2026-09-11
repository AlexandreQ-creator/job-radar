"""Testes de notifier.telegram.publicar_vaga — o protocolo completo de "o
que acontece com uma vaga aprovada", extraído de main.py::ciclo_de_busca
(ticket 03 de .scratch/melhorias-arquitetura/issues/).

Todas as dependências externas (notificação real, gravação no banco,
resumo por IA) são mockadas — o que se testa aqui é a decisão (imediato
vs. digest, qual notificar_vaga* chamar, ordem notificar-então-salvar),
não o efeito de rede/disco em si (já coberto por test_telegram.py e pelos
testes de database/)."""

from unittest.mock import patch

from core.job import Job
from core.perfis import PERFIL_BR
from notifier.telegram import publicar_vaga


def vaga(**overrides) -> Job:
    base = dict(
        titulo="Analista de Dados Pleno",
        empresa="Empresa Teste",
        local="São Paulo, SP",
        link="https://exemplo.com/vaga",
        site="Teste",
        modalidade="Remoto",
    )
    base.update(overrides)
    job = Job(**base)
    job.relevancia = overrides.get("relevancia", 8)
    return job


@patch("notifier.telegram.salvar_vaga")
@patch("notifier.telegram.gerar_resumo", return_value="resumo gerado")
@patch("notifier.telegram.notificar_vaga", return_value=True)
def test_relevancia_alta_notifica_e_salva_sem_digest(mock_notificar, mock_resumo, mock_salvar):
    vaga_alta = vaga(relevancia=8)
    assert publicar_vaga(vaga_alta, PERFIL_BR) is True

    mock_resumo.assert_called_once_with(vaga_alta)
    mock_notificar.assert_called_once_with(vaga_alta)
    mock_salvar.assert_called_once_with(vaga_alta, perfil_chave=PERFIL_BR.chave, exploratoria=False)
    assert vaga_alta.resumo_ia == "resumo gerado"


@patch("notifier.telegram.salvar_vaga")
@patch("notifier.telegram.gerar_resumo")
@patch("notifier.telegram.notificar_vaga")
def test_relevancia_baixa_vai_pro_digest_sem_notificar(mock_notificar, mock_resumo, mock_salvar):
    vaga_baixa = vaga(relevancia=3)
    assert publicar_vaga(vaga_baixa, PERFIL_BR) is True

    mock_notificar.assert_not_called()
    mock_resumo.assert_not_called()
    mock_salvar.assert_called_once_with(
        vaga_baixa, perfil_chave=PERFIL_BR.chave, digest_pendente=True, exploratoria=False
    )


@patch("notifier.telegram.salvar_vaga")
@patch("notifier.telegram.gerar_resumo", return_value="")
@patch("notifier.telegram.notificar_vaga", return_value=False)
def test_falha_ao_notificar_nao_salva_e_devolve_false(mock_notificar, mock_resumo, mock_salvar):
    vaga_alta = vaga(relevancia=9)
    assert publicar_vaga(vaga_alta, PERFIL_BR) is False

    mock_salvar.assert_not_called()


@patch("notifier.telegram.salvar_vaga")
@patch("notifier.telegram.gerar_resumo", return_value="")
@patch("notifier.telegram.notificar_vaga_exploratoria", return_value=True)
@patch("notifier.telegram.notificar_vaga")
def test_exploratoria_chama_notificar_vaga_exploratoria_nao_a_normal(
    mock_notificar_normal, mock_notificar_exp, mock_resumo, mock_salvar
):
    vaga_alta = vaga(relevancia=8)
    assert publicar_vaga(vaga_alta, PERFIL_BR, exploratoria=True) is True

    mock_notificar_exp.assert_called_once_with(vaga_alta)
    mock_notificar_normal.assert_not_called()
    mock_salvar.assert_called_once_with(vaga_alta, perfil_chave=PERFIL_BR.chave, exploratoria=True)


@patch("notifier.telegram.salvar_vaga")
@patch("notifier.telegram.gerar_resumo")
@patch("notifier.telegram.notificar_vaga")
def test_vaga_antiga_vai_pro_digest_mesmo_com_relevancia_alta(mock_notificar, mock_resumo, mock_salvar):
    # publicacao_antiga depende de publicado_em + data — usar um texto que
    # o parser de core/job.py reconheça como antigo o bastante.
    vaga_antiga = vaga(relevancia=9, publicado_em="Há 6 meses")
    assert vaga_antiga.publicacao_antiga is True

    assert publicar_vaga(vaga_antiga, PERFIL_BR) is True
    mock_notificar.assert_not_called()
    mock_salvar.assert_called_once_with(
        vaga_antiga, perfil_chave=PERFIL_BR.chave, digest_pendente=True, exploratoria=False
    )
