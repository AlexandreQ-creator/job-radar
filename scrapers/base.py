
from abc import ABC, abstractmethod

from core.job import Job


class BaseScraper(ABC):

    @abstractmethod
    def buscar_vagas(self) -> list[Job]:
        pass