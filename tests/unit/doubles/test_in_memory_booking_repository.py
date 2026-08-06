"""`InMemoryBookingRepository` — a dupla que sustenta os testes das tasks 07 a 09.

As três consultas carregam regra de negócio de verdade: RN-01 define o que é reserva ativa, RN-02
define o que é sobreposição e RN-08 define o que é "a mesma semana". Errar qualquer uma delas aqui
faria os casos de uso passarem contra um comportamento que a task 10 não vai reproduzir.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.value_objects.time_slot import TimeSlot
from tests.doubles.in_memory_repositories import InMemoryBookingRepository

SOLICITANTE = "2019001234"
OUTRO = "2020005678"

# 20/08/2026 é quinta-feira: semana ISO 34, de segunda 17/08 a domingo 23/08.
QUINTA = date(2026, 8, 20)
DOMINGO = date(2026, 8, 23)
SEGUNDA_SEGUINTE = date(2026, 8, 24)

ATIVOS = [BookingStatus.PENDING, BookingStatus.APPROVED]
INATIVOS = [BookingStatus.REJECTED, BookingStatus.CANCELLED]


def intervalo(dia: date, inicio: int, fim: int) -> TimeSlot:
    return TimeSlot(datetime.combine(dia, datetime.min.time()) + timedelta(hours=inicio),
                    datetime.combine(dia, datetime.min.time()) + timedelta(hours=fim))


def reserva(
    slot: TimeSlot,
    *,
    space_code: str = "LAB-01",
    requester_id: str = SOLICITANTE,
    status: BookingStatus = BookingStatus.APPROVED,
) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=space_code,
        requester_id=requester_id,
        slot=slot,
        purpose="Aula prática de Redes de Computadores",
        attendees=25,
        status=status,
        created_at=datetime(2026, 8, 5, 9, 0),
    )


def repositorio(*reservas: Booking) -> InMemoryBookingRepository:
    repo = InMemoryBookingRepository()
    for r in reservas:
        repo.add(r)
    return repo


def ids(reservas: list[Booking]) -> set[UUID]:
    return {r.id for r in reservas}


# --- add, update e find_by_id ----------------------------------------------------------------


def test_reserva_adicionada_pode_ser_encontrada() -> None:
    guardada = reserva(intervalo(QUINTA, 14, 16))
    assert repositorio(guardada).find_by_id(guardada.id) is guardada


def test_buscar_identificador_inexistente_devolve_nulo() -> None:
    """A interface devolve `Booking | None`; quem levanta `BookingNotFound` é o caso de uso."""
    assert repositorio(reserva(intervalo(QUINTA, 14, 16))).find_by_id(uuid4()) is None


def test_update_substitui_a_reserva_guardada() -> None:
    """É como a task 09 persiste uma transição: transiciona a entidade e manda de volta."""
    guardada = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.PENDING)
    repo = repositorio(guardada)

    guardada.status = BookingStatus.APPROVED
    repo.update(guardada)

    encontrada = repo.find_by_id(guardada.id)
    assert encontrada is not None
    assert encontrada.status is BookingStatus.APPROVED


def test_update_nao_cria_reserva_nova() -> None:
    guardada = reserva(intervalo(QUINTA, 14, 16))
    repo = repositorio(guardada)
    repo.update(guardada)
    assert len(repo.list_by_space_and_date("LAB-01", QUINTA)) == 1


# --- find_active_overlapping — RN-01 e RN-02 -------------------------------------------------


def test_sobreposicao_encontra_a_reserva_conflitante() -> None:
    """RN-02."""
    ocupada = reserva(intervalo(QUINTA, 14, 16))
    repo = repositorio(ocupada)
    assert ids(repo.find_active_overlapping("LAB-01", intervalo(QUINTA, 15, 17))) == {ocupada.id}


def test_intervalos_que_apenas_se_tocam_nao_conflitam() -> None:
    """RN-02 — uma reserva das 8h às 10h convive com outra das 10h às 12h."""
    repo = repositorio(reserva(intervalo(QUINTA, 8, 10)))
    assert repo.find_active_overlapping("LAB-01", intervalo(QUINTA, 10, 12)) == []


@pytest.mark.parametrize("status", ATIVOS, ids=lambda s: str(s))
def test_reserva_ativa_ocupa_o_intervalo(status: BookingStatus) -> None:
    """RN-01 — ativa é `PENDING` ou `APPROVED`."""
    ocupada = reserva(intervalo(QUINTA, 14, 16), status=status)
    repo = repositorio(ocupada)
    assert ids(repo.find_active_overlapping("LAB-01", intervalo(QUINTA, 14, 16))) == {ocupada.id}


@pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
def test_reserva_em_estado_terminal_libera_o_intervalo(status: BookingStatus) -> None:
    """RN-01 — uma reserva cancelada devolve o horário para novas solicitações."""
    repo = repositorio(reserva(intervalo(QUINTA, 14, 16), status=status))
    assert repo.find_active_overlapping("LAB-01", intervalo(QUINTA, 14, 16)) == []


def test_sobreposicao_e_por_espaco() -> None:
    """Dois espaços diferentes no mesmo horário não conflitam entre si."""
    repo = repositorio(reserva(intervalo(QUINTA, 14, 16), space_code="SALA-01"))
    assert repo.find_active_overlapping("LAB-01", intervalo(QUINTA, 14, 16)) == []


def test_espaco_sem_reserva_alguma_nao_conflita() -> None:
    assert InMemoryBookingRepository().find_active_overlapping("LAB-01", intervalo(QUINTA, 14, 16)) == []


# --- find_active_by_requester_in_week — RN-08 ------------------------------------------------


def test_reservas_da_semana_do_solicitante() -> None:
    """RN-08 — a semana ISO de referência, e só as do próprio solicitante."""
    minha = reserva(intervalo(QUINTA, 14, 16))
    repo = repositorio(minha, reserva(intervalo(QUINTA, 8, 10), requester_id=OUTRO))
    encontradas = repo.find_active_by_requester_in_week(SOLICITANTE, datetime(2026, 8, 20, 9))
    assert ids(encontradas) == {minha.id}


def test_domingo_ainda_esta_na_semana_e_a_segunda_seguinte_nao() -> None:
    """RN-08 — a semana ISO vai de segunda a domingo; a fronteira é entre os dois."""
    no_domingo = reserva(intervalo(DOMINGO, 14, 16))
    na_semana_seguinte = reserva(intervalo(SEGUNDA_SEGUINTE, 14, 16))
    repo = repositorio(no_domingo, na_semana_seguinte)

    encontradas = repo.find_active_by_requester_in_week(SOLICITANTE, datetime(2026, 8, 20, 9))
    assert ids(encontradas) == {no_domingo.id}


@pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
def test_reserva_inativa_nao_conta_na_semana(status: BookingStatus) -> None:
    """RN-08 — só reservas ativas consomem o teto semanal."""
    repo = repositorio(reserva(intervalo(QUINTA, 14, 16), status=status))
    assert repo.find_active_by_requester_in_week(SOLICITANTE, datetime(2026, 8, 20, 9)) == []


def test_semana_sem_reserva_devolve_lista_vazia() -> None:
    repo = repositorio(reserva(intervalo(SEGUNDA_SEGUINTE, 14, 16)))
    assert repo.find_active_by_requester_in_week(SOLICITANTE, datetime(2026, 8, 20, 9)) == []


# --- list_by_space_and_date — UC-03 ----------------------------------------------------------


def test_agenda_do_dia_traz_as_reservas_ativas_do_espaco() -> None:
    manha = reserva(intervalo(QUINTA, 8, 10))
    tarde = reserva(intervalo(QUINTA, 14, 16))
    repo = repositorio(manha, tarde, reserva(intervalo(QUINTA, 9, 11), space_code="SALA-01"))
    assert ids(repo.list_by_space_and_date("LAB-01", QUINTA)) == {manha.id, tarde.id}


@pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
def test_agenda_do_dia_ignora_reserva_em_estado_terminal(status: BookingStatus) -> None:
    """UC-03 — canceladas e rejeitadas não aparecem: o horário está livre."""
    repo = repositorio(reserva(intervalo(QUINTA, 14, 16), status=status))
    assert repo.list_by_space_and_date("LAB-01", QUINTA) == []


def test_agenda_do_dia_ignora_outro_dia() -> None:
    repo = repositorio(reserva(intervalo(QUINTA, 14, 16)))
    assert repo.list_by_space_and_date("LAB-01", DOMINGO) == []


def test_reserva_que_atravessa_a_meia_noite_aparece_nos_dois_dias() -> None:
    """UC-03 serve para achar as faixas livres: uma reserva das 22h às 2h ocupa as duas manhãs."""
    virada = reserva(
        TimeSlot(datetime(2026, 8, 20, 22), datetime(2026, 8, 21, 2))
    )
    repo = repositorio(virada)
    assert ids(repo.list_by_space_and_date("LAB-01", QUINTA)) == {virada.id}
    assert ids(repo.list_by_space_and_date("LAB-01", date(2026, 8, 21))) == {virada.id}


def test_reserva_que_termina_a_meia_noite_nao_invade_o_dia_seguinte() -> None:
    """A fronteira é a mesma da RN-02: tocar a borda não é ocupar."""
    ate_meia_noite = reserva(
        TimeSlot(datetime(2026, 8, 20, 22), datetime(2026, 8, 21, 0))
    )
    repo = repositorio(ate_meia_noite)
    assert ids(repo.list_by_space_and_date("LAB-01", QUINTA)) == {ate_meia_noite.id}
    assert repo.list_by_space_and_date("LAB-01", date(2026, 8, 21)) == []


def test_dia_sem_reserva_devolve_lista_vazia() -> None:
    assert InMemoryBookingRepository().list_by_space_and_date("LAB-01", QUINTA) == []
