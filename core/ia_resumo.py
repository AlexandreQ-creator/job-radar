"""Resumo de compatibilidade gerado por IA — a "Fase 3" citada no TODO
histórico de notifier/telegram.py::notificar_vaga. Autoria: fork do usuário
deste projeto. Não é parte do motor de filtro/scraping original do projeto (ver
README.md para a atribuição completa a Liliam Kezia Oliveira Souza) — é uma
camada nova, adicionada por cima, que só explica em linguagem natural por
que uma vaga JÁ aprovada pelo filtro por regra é relevante. Nunca decide
nem pontua nada: o score em Job.relevancia (core/job.py) continua sendo
100% determinístico, calculado antes desta camada rodar.

Desligado por padrão. Sem ANTHROPIC_API_KEY no .env, gerar_resumo() devolve
"" na primeira linha, sem importar o SDK nem tentar rede — o projeto
continua funcionando exatamente como antes pra quem não configurar a
chave. Só roda pras vagas que já bateram o limiar de notificação imediata
(ver LIMIAR_DIGEST_IMEDIATO em config.py e o chamador em main.py), não pra
todo mundo que passa no filtro — mantém o custo de API previsível (dezenas
de chamadas por ciclo, não centenas).
"""

import os

from core.logger import get_logger

logger = get_logger()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Haiku por padrão: modelo mais barato/rápido da família Claude — a tarefa
# aqui é resumir 1-2 frases a partir de um contexto curto, não raciocínio
# complexo. Configurável via env pra quem quiser trocar sem editar código.
MODELO_RESUMO_IA = os.getenv("JOBRADAR_MODELO_IA", "claude-haiku-4-5-20251001")

# Corta a descrição da vaga antes de mandar pro modelo — resumo de 1-2
# frases não precisa do texto inteiro, e a vaga já foi aprovada pelo filtro
# por regra antes de chegar aqui (isto é só explicação, não é decisão).
# Mantém o custo de tokens por chamada baixo e prevísivel.
_LIMITE_CHARS_DESCRICAO = 800

_PROMPT_SISTEMA = (
    "Você resume, em português do Brasil, por que uma vaga de emprego já "
    "aprovada por um filtro de regras é relevante para o candidato. "
    "Responda em no máximo 2 frases curtas e diretas, sem saudação nem "
    "encerramento, sem repetir o título do cargo literalmente. Baseie-se "
    "só no que foi fornecido no contexto — nunca invente responsabilidade, "
    "requisito, benefício ou faixa salarial que não esteja no texto."
)


def gerar_resumo(job) -> str:
    """Devolve 1-2 frases explicando por que `job` é relevante, a partir do
    título, do motivo do score (Job.motivo, já calculado pelo filtro por
    regra) e — quando a fonte expõe — da descrição da vaga. Devolve ""
    quando a IA está desligada (sem chave) ou quando qualquer coisa falha.

    Nunca lança exceção: falha de rede, rate limit, chave inválida ou
    resposta vazia da API não pode derrubar notificar_vaga() nem o ciclo de
    busca inteiro — mesmo princípio de enviar_mensagem() em
    notifier/telegram.py (falha aqui é log + seguir em frente, a vaga já é
    válida e relevante mesmo sem o resumo)."""
    if not ANTHROPIC_API_KEY:
        return ""

    try:
        import anthropic
    except ImportError:
        logger.warning(
            "ANTHROPIC_API_KEY configurada mas o pacote 'anthropic' não está "
            "instalado (pip install anthropic) — resumo de IA desligado neste ciclo."
        )
        return ""

    contexto = f"Cargo: {job.titulo}\nEmpresa: {job.empresa}\nMotivo do score do filtro: {job.motivo}"
    if job.descricao:
        contexto += f"\nDescrição (trecho): {job.descricao[:_LIMITE_CHARS_DESCRICAO]}"

    try:
        cliente = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resposta = cliente.messages.create(
            model=MODELO_RESUMO_IA,
            max_tokens=120,
            system=_PROMPT_SISTEMA,
            messages=[{"role": "user", "content": contexto}],
        )
        texto = "".join(
            bloco.text for bloco in resposta.content if getattr(bloco, "type", None) == "text"
        ).strip()
        return texto
    except Exception as e:
        logger.warning(f"Falha ao gerar resumo de IA para '{job.titulo}': {type(e).__name__} ({e})")
        return ""
