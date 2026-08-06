"""UC-04 — solicitar reserva.

O caso de uso onde os três padrões colaboram, e o único teste do projeto que os vê trabalhando
juntos: o Strategy decide o status inicial e as restrições, o State governa a reserva que nasce, o
Observer publica o fato. Os três aparecem separados em blocos próprios mais abaixo — são eles que a
defesa cita.

Todas as datas são fixas. Nenhum `datetime.now()` aqui nem no código sob teste: o instante entra
pelo comando, e é isso que faz "24h de antecedência" ter o mesmo resultado às 3h da manhã do dia da
entrega.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from agendalab.application.dto import RequestBookingCommand
from agendalab.application.use_cases import request_booking
from agendalab.application.use_cases.request_booking import RequestBooking
from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.entities.space import Space, SpaceKind
from agendalab.domain.errors import (
    CapacityExceeded,
    DomainError,
    InactiveSpace,
    InvalidTimeSlot,
    PolicyViolation,
    ScheduleConflict,
    SpaceNotFound,
)
from agendalab.domain.events.booking_events import BookingRequested
from agendalab.domain.events.publisher import EventPublisher
from agendalab.domain.value_objects.time_slot import TimeSlot
from tests.doubles.in_memory_repositories import (
    InMemoryBookingRepository,
    InMemorySpaceRepository,
)
from tests.doubles.spy_observer import SpyObserver

SOLICITANTE = "2019001234"
OUTRO_SOLICITANTE = "2020005678"

AGORA = datetime(2026, 8, 5, 9, 0)  # quarta-feira
PASSADO = datetime(2026, 8, 1, 8, 0)

# 20/08/2026 é quinta-feira: semana ISO 34, de segunda 17/08 a domingo 23/08.
QUINTA = datetime(2026, 8, 20, 14, 0)
SEGUNDA = datetime(2026, 8, 17, 8, 0)
SEMANA_SEGUINTE = datetime(2026, 8, 24, 8, 0)  # semana ISO 35

# Antecedências curtas, para exercitar as políticas que exigem aviso prévio.
DAQUI_A_11H = datetime(2026, 8, 5, 20, 0)
DAQUI_A_2_DIAS = datetime(2026, 8, 7, 9, 0)

SALA = Space(code="S-01", name="Sala 101", kind=SpaceKind.CLASSROOM, capacity=40)
OUTRA_SALA = Space(code="S-02", name="Sala 102", kind=SpaceKind.CLASSROOM, capacity=40)
SALA_INATIVA = Space(
    code="S-09", name="Sala em reforma", kind=SpaceKind.CLASSROOM, capacity=40, active=False
)
LABORATORIO = Space(code="L-01", name="Lab. de Redes", kind=SpaceKind.LAB, capacity=30)
AUDITORIO = Space(code="A-01", name="Auditório Central", kind=SpaceKind.AUDITORIUM, capacity=200)

CATALOGO = (SALA, OUTRA_SALA, SALA_INATIVA, LABORATORIO, AUDITORIO)


def intervalo(inicio: datetime, horas: float) -> TimeSlot:
    return TimeSlot(inicio, inicio + timedelta(hours=horas))


def comando(
    *,
    space_code: str = SALA.code,
    requester_id: str = SOLICITANTE,
    slot: TimeSlot | None = None,
    purpose: str = "Monitoria de Cálculo I",
    attendees: int = 25,
    now: datetime = AGORA,
) -> RequestBookingCommand:
    return RequestBookingCommand(
        space_code=space_code,
        requester_id=requester_id,
        slot=slot if slot is not None else intervalo(QUINTA, 2),
        purpose=purpose,
        attendees=attendees,
        now=now,
    )


def reserva(
    slot: TimeSlot,
    *,
    space_code: str = SALA.code,
    requester_id: str = SOLICITANTE,
    status: BookingStatus = BookingStatus.APPROVED,
) -> Booking:
    return Booking(
        id=uuid4(),
        space_code=space_code,
        requester_id=requester_id,
        slot=slot,
        purpose="Aula já agendada",
        attendees=20,
        status=status,
        created_at=AGORA,
    )


class Cenario:
    """O caso de uso montado com as três duplas, e o acesso a elas para inspecionar o resultado."""

    def __init__(self, *, espacos: tuple[Space, ...], reservas: tuple[Booking, ...]) -> None:
        self.spaces = InMemorySpaceRepository()
        for espaco in espacos:
            self.spaces.add(espaco)

        self.bookings = InMemoryBookingRepository()
        for existente in reservas:
            self.bookings.add(existente)

        self.espiao = SpyObserver()
        publicador = EventPublisher()
        publicador.subscribe(self.espiao)

        self.solicitar = RequestBooking(self.spaces, self.bookings, publicador)

    def agenda_de(self, cmd: RequestBookingCommand) -> list[Booking]:
        """As reservas ativas do espaço e dia do comando — como contar o que foi persistido."""
        return self.bookings.list_by_space_and_date(cmd.space_code, cmd.slot.start_at.date())


def cenario(
    *, espacos: tuple[Space, ...] = CATALOGO, reservas: tuple[Booking, ...] = ()
) -> Cenario:
    return Cenario(espacos=espacos, reservas=reservas)


# --- passo 1: o espaço precisa existir ---------------------------------------------------------


def test_solicitar_em_espaco_inexistente_e_recusado() -> None:
    with pytest.raises(SpaceNotFound, match="NAO-EXISTE"):
        cenario().solicitar.execute(comando(space_code="NAO-EXISTE"))


# --- passo 2: RN-04, o intervalo começa no futuro ----------------------------------------------


def test_reserva_no_passado_e_recusada() -> None:
    with pytest.raises(InvalidTimeSlot) as erro:
        cenario().solicitar.execute(comando(slot=intervalo(PASSADO, 2)))
    assert erro.value.rule == "RN-04"


def test_reserva_que_comeca_exatamente_agora_e_recusada() -> None:
    """Estar no futuro exclui o próprio instante: às 9h em ponto, uma reserva das 9h já começou."""
    with pytest.raises(InvalidTimeSlot):
        cenario().solicitar.execute(comando(slot=intervalo(AGORA, 2)))


def test_reserva_que_comeca_logo_depois_de_agora_e_aceita() -> None:
    """A fronteira do outro lado: um minuto de futuro basta para a RN-04."""
    daqui_a_pouco = AGORA + timedelta(minutes=1)
    criada = cenario().solicitar.execute(comando(slot=intervalo(daqui_a_pouco, 2)))
    assert criada.slot.start_at == daqui_a_pouco


def test_a_busca_do_espaco_vem_antes_da_validacao_do_intervalo() -> None:
    """Espaço inexistente e data no passado: o erro é o do espaço, que é o primeiro passo."""
    with pytest.raises(SpaceNotFound):
        cenario().solicitar.execute(
            comando(space_code="NAO-EXISTE", slot=intervalo(PASSADO, 2))
        )


# --- passo 3: RN-05, espaço inativo ------------------------------------------------------------


def test_espaco_inativo_nao_aceita_nova_reserva() -> None:
    with pytest.raises(InactiveSpace) as erro:
        cenario().solicitar.execute(comando(space_code=SALA_INATIVA.code))
    assert erro.value.rule == "RN-05"


# --- passo 4: RN-06, capacidade ----------------------------------------------------------------


def test_participantes_acima_da_capacidade_e_recusado() -> None:
    with pytest.raises(CapacityExceeded) as erro:
        cenario().solicitar.execute(comando(attendees=SALA.capacity + 1))
    assert erro.value.rule == "RN-06"


def test_participantes_exatamente_na_capacidade_e_aceito() -> None:
    """A regra é "não exceder": lotar o espaço é legítimo."""
    criada = cenario().solicitar.execute(comando(attendees=SALA.capacity))
    assert criada.attendees == SALA.capacity


# --- passo 5: RN-01 e RN-02, conflito de horário -----------------------------------------------


def test_conflito_com_reserva_ativa_e_recusado() -> None:
    ocupado = cenario(reservas=(reserva(intervalo(QUINTA, 2)),))
    with pytest.raises(ScheduleConflict) as erro:
        ocupado.solicitar.execute(comando(slot=intervalo(QUINTA, 2)))
    assert erro.value.rule == "RN-01"


def test_sobreposicao_parcial_tambem_e_conflito() -> None:
    ocupado = cenario(reservas=(reserva(intervalo(QUINTA, 2)),))
    with pytest.raises(ScheduleConflict):
        ocupado.solicitar.execute(comando(slot=intervalo(QUINTA + timedelta(hours=1), 2)))


def test_reservas_que_apenas_se_tocam_nas_bordas_convivem() -> None:
    """RN-02 — quem termina às 16h não conflita com quem começa às 16h."""
    ocupado = cenario(reservas=(reserva(intervalo(QUINTA, 2)),))
    criada = ocupado.solicitar.execute(comando(slot=intervalo(QUINTA + timedelta(hours=2), 2)))
    assert criada.slot.start_at == QUINTA + timedelta(hours=2)


@pytest.mark.parametrize("status", [BookingStatus.CANCELLED, BookingStatus.REJECTED])
def test_reserva_encerrada_libera_o_intervalo(status: BookingStatus) -> None:
    """RN-01 — só `PENDING` e `APPROVED` ocupam. O horário volta a ser solicitável."""
    liberado = cenario(reservas=(reserva(intervalo(QUINTA, 2), status=status),))
    criada = liberado.solicitar.execute(comando(slot=intervalo(QUINTA, 2)))
    assert criada.status is BookingStatus.APPROVED


def test_reserva_no_mesmo_horario_de_outro_espaco_nao_conflita() -> None:
    vizinho = cenario(reservas=(reserva(intervalo(QUINTA, 2), space_code=OUTRA_SALA.code),))
    criada = vizinho.solicitar.execute(comando(slot=intervalo(QUINTA, 2)))
    assert criada.space_code == SALA.code


# --- passo 6: RN-07 a RN-10, as políticas ------------------------------------------------------


def test_sala_de_aula_acima_do_teto_semanal_e_recusada() -> None:
    """RN-08 — 6h já reservadas na semana mais 4h solicitadas passam do teto de 8h."""
    semana_cheia = cenario(
        reservas=(reserva(intervalo(SEGUNDA, 6), space_code=SALA.code),)
    )
    with pytest.raises(PolicyViolation) as erro:
        semana_cheia.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert erro.value.rule == "RN-08"


def test_laboratorio_sem_antecedencia_minima_e_recusado() -> None:
    """RN-09 — 11h de aviso não bastam para quem exige 24h."""
    with pytest.raises(PolicyViolation) as erro:
        cenario().solicitar.execute(
            comando(space_code=LABORATORIO.code, slot=intervalo(DAQUI_A_11H, 2))
        )
    assert erro.value.rule == "RN-09"


def test_laboratorio_longo_demais_e_recusado() -> None:
    """RN-09 — o teto de 4h por sessão."""
    with pytest.raises(PolicyViolation) as erro:
        cenario().solicitar.execute(
            comando(space_code=LABORATORIO.code, slot=intervalo(QUINTA, 5))
        )
    assert erro.value.rule == "RN-09"


def test_auditorio_sem_antecedencia_minima_e_recusado() -> None:
    """RN-10 — dois dias de aviso não bastam para quem exige três."""
    with pytest.raises(PolicyViolation) as erro:
        cenario().solicitar.execute(
            comando(space_code=AUDITORIO.code, slot=intervalo(DAQUI_A_2_DIAS, 2))
        )
    assert erro.value.rule == "RN-10"


def test_auditorio_com_poucos_participantes_e_recusado() -> None:
    """RN-10 — o auditório é para eventos de porte."""
    with pytest.raises(PolicyViolation) as erro:
        cenario().solicitar.execute(comando(space_code=AUDITORIO.code, attendees=5))
    assert erro.value.rule == "RN-10"


# --- o contexto da política: o filtro por tipo de espaço ---------------------------------------
#
# A RN-08 conta horas "em espaços do tipo CLASSROOM". `Booking` guarda `space_code`, não `kind`, e a
# política não tem como resolver um no outro — quem monta o contexto resolve. Estes testes são os
# que provam que o caso de uso fez isso, e falhariam se ele repassasse a semana inteira sem filtrar.


def test_horas_em_laboratorio_nao_contam_no_teto_de_sala_de_aula() -> None:
    """6h de laboratório na mesma semana; a sala continua com as 8h dela inteiras."""
    semana = cenario(reservas=(reserva(intervalo(SEGUNDA, 6), space_code=LABORATORIO.code),))
    criada = semana.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert criada.status is BookingStatus.APPROVED


def test_horas_em_outra_sala_de_aula_contam_no_teto() -> None:
    """O teto é por solicitante e por tipo, não por espaço: trocar de sala não zera a conta."""
    semana = cenario(reservas=(reserva(intervalo(SEGUNDA, 6), space_code=OUTRA_SALA.code),))
    with pytest.raises(PolicyViolation) as erro:
        semana.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert erro.value.rule == "RN-08"


def test_horas_de_outro_solicitante_nao_contam_no_teto() -> None:
    semana = cenario(
        reservas=(reserva(intervalo(SEGUNDA, 6), requester_id=OUTRO_SOLICITANTE),)
    )
    criada = semana.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert criada.status is BookingStatus.APPROVED


def test_horas_de_outra_semana_nao_contam_no_teto() -> None:
    """Semana ISO 35 não influencia o teto da 34."""
    semana = cenario(reservas=(reserva(intervalo(SEMANA_SEGUINTE, 6)),))
    criada = semana.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert criada.status is BookingStatus.APPROVED


def test_reserva_de_espaco_desconhecido_e_ignorada_no_contexto() -> None:
    """Uma reserva órfã não tem tipo para comparar, e não pode derrubar uma solicitação válida."""
    orfa = reserva(intervalo(SEGUNDA, 6), space_code="ESPACO-QUE-SUMIU")
    semana = cenario(reservas=(orfa,))
    criada = semana.solicitar.execute(comando(slot=intervalo(QUINTA, 4)))
    assert criada.status is BookingStatus.APPROVED


# --- passo 7: Strategy — o status inicial vem da política --------------------------------------


@pytest.mark.parametrize(
    ("espaco", "esperado"),
    [
        (SALA, BookingStatus.APPROVED),
        (LABORATORIO, BookingStatus.PENDING),
        (AUDITORIO, BookingStatus.PENDING),
    ],
    ids=[SALA.kind, LABORATORIO.kind, AUDITORIO.kind],
)
def test_o_status_inicial_vem_da_politica_do_tipo_de_espaco(
    espaco: Space, esperado: BookingStatus
) -> None:
    """O teste que demonstra o Strategy: mesmo comando, mesmo caso de uso, três resultados.

    Sala de aula tem aprovação automática (RN-08); laboratório e auditório exigem aval de gestor
    (RN-09 e RN-10). O `RequestBooking` não sabe disso — quem responde é a política.
    """
    criada = cenario().solicitar.execute(comando(space_code=espaco.code))
    assert criada.status is esperado


def test_o_caso_de_uso_nao_menciona_nenhum_tipo_de_espaco() -> None:
    """O critério de aceite do ADR-0004, como verificação em vez de conferência de olho.

    Um `if kind is SpaceKind.LAB` no caso de uso funcionaria e passaria em todos os testes acima —
    e teria matado o Strategy. É esta ausência que a defesa cita.
    """
    fonte = Path(request_booking.__file__).read_text(encoding="utf-8")
    assert "SpaceKind" not in fonte
    for kind in SpaceKind:
        assert kind.name not in fonte, f"o caso de uso menciona {kind.name}"


# --- passo 8: persistência e evento ------------------------------------------------------------


def test_a_reserva_criada_carrega_os_dados_do_comando() -> None:
    criada = cenario().solicitar.execute(
        comando(slot=intervalo(QUINTA, 2), purpose="Aula de Redes", attendees=30)
    )
    assert (criada.space_code, criada.requester_id, criada.purpose, criada.attendees) == (
        SALA.code,
        SOLICITANTE,
        "Aula de Redes",
        30,
    )
    assert criada.slot == intervalo(QUINTA, 2)


def test_a_reserva_criada_fica_persistida() -> None:
    c = cenario()
    criada = c.solicitar.execute(comando())
    assert c.bookings.find_by_id(criada.id) is criada


def test_a_reserva_nasce_sem_trilha_de_decisao() -> None:
    """Ninguém decidiu nada ainda — nem quando a política já aprova automaticamente."""
    criada = cenario().solicitar.execute(comando())
    assert (criada.decided_by, criada.decided_at, criada.rejection_reason) == (None, None, None)


def test_o_instante_de_criacao_vem_do_comando() -> None:
    """Nenhum relógio é lido: `created_at` é o `now` recebido."""
    assert cenario().solicitar.execute(comando()).created_at == AGORA


def test_cada_reserva_recebe_identidade_propria() -> None:
    c = cenario()
    primeira = c.solicitar.execute(comando(slot=intervalo(QUINTA, 2)))
    segunda = c.solicitar.execute(comando(slot=intervalo(QUINTA + timedelta(hours=3), 2)))
    assert primeira.id != segunda.id


# --- Observer: RN-15 ---------------------------------------------------------------------------


def test_o_caminho_feliz_publica_o_evento_de_solicitacao() -> None:
    c = cenario()
    criada = c.solicitar.execute(comando())

    evento = c.espiao.unico
    assert isinstance(evento, BookingRequested)
    assert (evento.booking_id, evento.space_code, evento.requester_id, evento.occurred_at) == (
        criada.id,
        SALA.code,
        SOLICITANTE,
        AGORA,
    )


def test_o_instante_do_evento_vem_do_comando() -> None:
    """`occurred_at` é o `now` recebido, como `created_at`: o domínio não lê relógio."""
    c = cenario()
    c.solicitar.execute(comando())
    assert c.espiao.unico.occurred_at == AGORA


def test_uma_solicitacao_publica_exatamente_um_evento() -> None:
    c = cenario()
    c.solicitar.execute(comando())
    assert len(c.espiao.recebidos) == 1


def test_a_operacao_sobrevive_a_um_observador_quebrado() -> None:
    """Notificação é efeito colateral: um canal fora do ar não desfaz uma reserva legítima."""

    class ObservadorQuebrado:
        def handle(self, event: BookingRequested) -> None:
            raise RuntimeError("o canal de notificação caiu")

    spaces = InMemorySpaceRepository()
    spaces.add(SALA)
    bookings = InMemoryBookingRepository()
    publicador = EventPublisher()
    publicador.subscribe(ObservadorQuebrado())

    criada = RequestBooking(spaces, bookings, publicador).execute(comando())

    assert bookings.find_by_id(criada.id) is criada


# --- o que acontece quando a solicitação é recusada ---------------------------------------------
#
# Um caso de uso que publicasse o evento antes de validar, ou que persistisse e só depois checasse a
# política, passaria em todos os testes de recusa acima — o erro certo seria levantado. Estes dois
# testes cobrem o rastro que ele deixaria para trás.


def recusa_espaco_inexistente() -> tuple[Cenario, RequestBookingCommand]:
    return cenario(), comando(space_code="NAO-EXISTE")


def recusa_intervalo_no_passado() -> tuple[Cenario, RequestBookingCommand]:
    return cenario(), comando(slot=intervalo(PASSADO, 2))


def recusa_espaco_inativo() -> tuple[Cenario, RequestBookingCommand]:
    return cenario(), comando(space_code=SALA_INATIVA.code)


def recusa_capacidade_excedida() -> tuple[Cenario, RequestBookingCommand]:
    return cenario(), comando(attendees=SALA.capacity + 1)


def recusa_conflito_de_horario() -> tuple[Cenario, RequestBookingCommand]:
    return (
        cenario(reservas=(reserva(intervalo(QUINTA, 2)),)),
        comando(slot=intervalo(QUINTA, 2)),
    )


def recusa_da_politica() -> tuple[Cenario, RequestBookingCommand]:
    return cenario(), comando(space_code=AUDITORIO.code, attendees=5)


RECUSAS = [
    recusa_espaco_inexistente,
    recusa_intervalo_no_passado,
    recusa_espaco_inativo,
    recusa_capacidade_excedida,
    recusa_conflito_de_horario,
    recusa_da_politica,
]
IDS_DAS_RECUSAS = [f.__name__.removeprefix("recusa_") for f in RECUSAS]

MontarRecusa = Callable[[], tuple[Cenario, RequestBookingCommand]]


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nenhum_evento_e_publicado_quando_a_solicitacao_e_recusada(montar: MontarRecusa) -> None:
    """RN-15 — o evento é o registro de um fato. Uma reserva recusada não é fato nenhum."""
    c, cmd = montar()
    with pytest.raises(DomainError):
        c.solicitar.execute(cmd)
    assert c.espiao.recebidos == []


@pytest.mark.parametrize("montar", RECUSAS, ids=IDS_DAS_RECUSAS)
def test_nada_novo_e_persistido_quando_a_solicitacao_e_recusada(montar: MontarRecusa) -> None:
    c, cmd = montar()
    antes = len(c.agenda_de(cmd))
    with pytest.raises(DomainError):
        c.solicitar.execute(cmd)
    assert len(c.agenda_de(cmd)) == antes


# --- o comando ---------------------------------------------------------------------------------


def test_o_comando_e_imutavel() -> None:
    """Um caso de uso não reescreve o pedido que recebeu."""
    cmd = comando()
    with pytest.raises(AttributeError):
        cmd.attendees = 99  # type: ignore[misc]


def test_o_comando_carrega_o_instante_atual() -> None:
    """O relógio entra por aqui — é o que torna as políticas de antecedência testáveis."""
    assert "now" in RequestBookingCommand.__dataclass_fields__
