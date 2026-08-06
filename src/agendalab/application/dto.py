"""Comandos e consultas — a fronteira de entrada da camada de aplicação.

Um caso de uso recebe **um** objeto, não seis parâmetros soltos. A diferença aparece quando a
operação cresce: um campo novo entra no comando sem alterar a assinatura de `execute`, e quem chama
descobre pelo tipo o que precisa informar.

A distinção entre **comando** e **consulta** é intencional e segue a nomenclatura do CQS: um comando
altera o estado do sistema (`RegisterSpaceCommand`), uma consulta apenas o interroga
(`ListSpacesQuery`, `CheckAvailabilityQuery`). O nome já diz de que lado a operação está.

São todos imutáveis: um caso de uso não reescreve o pedido que recebeu. E são estruturas de dados
puras — nenhuma validação mora aqui, porque validar é do domínio (invariantes de entidade) ou da
borda HTTP (formato). As tasks 08 e 09 acrescentam os seus comandos neste mesmo arquivo.

Em tempo de execução este módulo não importa nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date, datetime

    from agendalab.domain.entities.space import SpaceKind
    from agendalab.domain.value_objects.time_slot import TimeSlot


@dataclass(frozen=True, slots=True)
class RegisterSpaceCommand:
    """UC-01. Não há campo `active`: o UC-01 diz que o espaço nasce ativo, sempre."""

    code: str
    name: str
    kind: SpaceKind
    capacity: int


@dataclass(frozen=True, slots=True)
class ListSpacesQuery:
    """UC-02. `None` em um filtro significa **não filtrar** por aquele critério — não "situação
    nula". É por isso que os dois campos são opcionais e uma `ListSpacesQuery()` vazia é a consulta
    que devolve tudo."""

    kind: SpaceKind | None = None
    active: bool | None = None


@dataclass(frozen=True, slots=True)
class CheckAvailabilityQuery:
    """UC-03. `day` é uma data, não um intervalo: a agenda é sempre de um dia inteiro."""

    space_code: str
    day: date


@dataclass(frozen=True, slots=True)
class RequestBookingCommand:
    """UC-04.

    `now` é o campo que merece explicação. O instante atual **entra pelo comando** em vez de ser
    lido no caso de uso, e não é preciosismo: as regras de antecedência (RN-09 e RN-10) comparam o
    início da reserva com o agora, e um `datetime.now()` dentro do domínio faria o mesmo teste dar
    resultados diferentes conforme a hora em que roda. Quem sabe que horas são é a borda HTTP.
    """

    space_code: str
    requester_id: str
    slot: TimeSlot
    purpose: str
    attendees: int
    now: datetime
