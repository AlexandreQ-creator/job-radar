
import json
from datetime import datetime, timezone
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from core.job import Job
from core.logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# Começa sem paginar, mesmo critério do LinkedInIntlScraper/WeWorkRemotely:
# pipeline novo, ainda não medido em produção — paginar depois de confirmar
# que vale o tempo de execução extra.
MAX_PAGINAS = 1

# simplify.jobs -> Remoto/Híbrido/Presencial (ver RegrasFiltro.cidades e
# Job.modalidade em core/job.py). "" pra qualquer valor não reconhecido —
# melhor deixar sem modalidade (cai no fallback de _confirma_remoto) do
# que arriscar mapear errado um rótulo novo que o site venha a usar.
_MAPA_MODALIDADE = {
    "remote": "Remoto",
    "hybrid": "Híbrido",
    "in person": "Presencial",
}


class SimplifyScraper(BaseScraper):
    """Busca vaga em simplify.jobs/jobs — agregador que, ao contrário do
    LinkedIn/Indeed, expõe RESULTADO GLOBAL numa busca só (não precisa
    repetir por país como LinkedInIntlScraper) e já classifica a modalidade
    de verdade por vaga (Remote/Hybrid/In Person), não um filtro de URL que
    pode divergir do anúncio — ver o caso real documentado em
    core/job.py:_modalidade_pelo_local (vaga da STG que passava como remota
    via f_WT=2 do LinkedIn sem ser).

    MEDIDO (Claude in Chrome, 2026-08-31): a página é Next.js renderizada
    no servidor — o HTML de /jobs?q=<termo> já vem com um
    <script id="__NEXT_DATA__"> contendo os resultados como JSON
    estruturado (props.pageProps.results.jobs), sem precisar esperar
    render client-side nem parsear seletor de card. Testado ao vivo:
    "SAP master data" devolveu 19 vagas reais (Elf Beauty, Mini-Circuits,
    Cardinal Health...) com título/empresa/local/modalidade/datas certos.

    LIMITAÇÃO CONHECIDA: o JSON da busca não traz a descrição completa da
    vaga (Job.descricao fica "" aqui) — só aparece numa chamada separada,
    disparada no client quando o usuário abre o painel de detalhe (não
    capturei o endpoint real, tentativas de fetch direto deram 404). Pra
    quem precisar do texto completo de uma vaga específica, abrir
    `https://simplify.jobs/jobs?job=<id>` manualmente funciona — é o
    "aprofundar página a página quando houver dúvida" combinado com o
    usuário, só que ainda não automatizado (ver SKILL.md do jobradar).
    """

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[Simplify] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Simplify] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = quote_plus(termo)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )
            try:
                for pagina in range(MAX_PAGINAS):
                    url = f"https://simplify.jobs/jobs?q={termo_url}&page={pagina + 1}"
                    page.goto(url, timeout=60000)

                    try:
                        page.wait_for_selector("#__NEXT_DATA__", state="attached", timeout=15000)
                    except Exception:
                        logger.warning(
                            f"[Simplify] Timeout em '{termo}' — __NEXT_DATA__ não apareceu "
                            "em 15s (possível bloqueio/anti-bot ou mudança na página)."
                        )
                        break

                    bruto = page.query_selector("#__NEXT_DATA__").inner_text()
                    try:
                        dados = json.loads(bruto)
                        jobs = dados["props"]["pageProps"]["results"]["jobs"]
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.warning(
                            f"[Simplify] __NEXT_DATA__ veio num formato inesperado pra "
                            f"'{termo}' ({e}) — provável mudança no site, não bloqueio."
                        )
                        break

                    if not jobs:
                        logger.info(f"[Simplify] 0 resultados confirmados para '{termo}'.")
                        break

                    for job in jobs:
                        try:
                            vagas.append(self._montar_job(job))
                        except Exception as e:
                            logger.warning(f"[Simplify] Erro ao processar vaga: {e}")
                            continue

            except Exception as e:
                logger.error(f"[Simplify] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas

    def _montar_job(self, job: dict) -> Job:
        titulo = (job.get("title") or "").strip()
        empresa = (job.get("company_name") or "Não informado").strip()
        locations = job.get("locations") or []
        local = "; ".join(locations) if locations else "Não informado"

        modalidade = _MAPA_MODALIDADE.get((job.get("travel_requirements") or "").strip().lower(), "")

        job_id = job.get("id") or job.get("posting_id") or ""
        link = f"https://simplify.jobs/jobs?job={job_id}"

        # start_date/updated_date vêm em epoch (segundos). Assumindo
        # start_date = quando o anúncio entrou no ar (é o que mais se
        # aproxima de "publicado em" — updated_date parece bater
        # atualização/republicação, não o post original; sem doc oficial
        # do endpoint, é a leitura mais provável dado que updated_date >=
        # start_date em toda amostra observada). Convertido pra ISO
        # (AAAA-MM-DD) — formato que Job.publicacao_antiga já sabe ler
        # (DIAS_PARA_PUBLICACAO_ANTIGA = 30), sem precisar de filtro novo:
        # vaga com mais de 30 dias cai automaticamente pro digest com aviso
        # "vaga antiga" em vez de notificação imediata (ver main.py).
        publicado_em = ""
        start_ts = job.get("start_date")
        if isinstance(start_ts, (int, float)) and start_ts > 0:
            try:
                publicado_em = datetime.fromtimestamp(start_ts, tz=timezone.utc).date().isoformat()
            except (ValueError, OSError):
                publicado_em = ""

        return Job(
            titulo=titulo,
            empresa=empresa,
            local=local,
            link=link,
            site="Simplify",
            publicado_em=publicado_em,
            modalidade=modalidade,
        )
