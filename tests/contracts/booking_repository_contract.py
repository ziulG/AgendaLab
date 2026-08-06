"""A bateria que toda implementação de `BookingRepository` precisa passar.

As três consultas daqui carregam regra de negócio de verdade: a RN-01 define o que é reserva ativa,
a RN-02 define o que é sobreposição e a RN-08 define o que é "a mesma semana". Uma implementação que
escreva `<=` onde deveria `<` numa das fronteiras produz reserva dupla, e o defeito não aparece em
nenhum teste de domínio — as fronteiras são o que esta bateria mais exercita.

Como no contrato de espaço, as comparações são por valor ou por identificador, nunca por identidade
de objeto: quem reconstrói a entidade a partir do banco devolve um objeto novo a cada consulta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from agendalab.domain.entities.booking import Booking, BookingStatus
from agendalab.domain.value_objects.time_slot import TimeSlot

if TYPE_CHECKING:
    from agendalab.domain.repositories import BookingRepository

SOLICITANTE = "2019001234"
OUTRO = "2020005678"

ESPACO = "LAB-01"
OUTRO_ESPACO = "SALA-01"

# 20/08/2026 é quinta-feira: semana ISO 34, de segunda 17/08 a domingo 23/08.
QUINTA = date(2026, 8, 20)
SEXTA = date(2026, 8, 21)
DOMINGO = date(2026, 8, 23)
SEGUNDA_SEGUINTE = date(2026, 8, 24)

MEIO_DA_QUINTA = datetime(2026, 8, 20, 9)

ATIVOS = [BookingStatus.PENDING, BookingStatus.APPROVED]
INATIVOS = [BookingStatus.REJECTED, BookingStatus.CANCELLED]


def intervalo(dia: date, inicio: int, fim: int) -> TimeSlot:
    meia_noite = datetime.combine(dia, datetime.min.time())
    return TimeSlot(meia_noite + timedelta(hours=inicio), meia_noite + timedelta(hours=fim))


def reserva(
    slot: TimeSlot,
    *,
    space_code: str = ESPACO,
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


def ids(reservas: list[Booking]) -> set[UUID]:
    return {r.id for r in reservas}


class BookingRepositoryContract:
    """Herde e implemente a fixture `bookings`."""

    @pytest.fixture
    def bookings(self) -> BookingRepository:
        raise NotImplementedError("a implementação sob teste precisa fornecer esta fixture")

    def povoar(self, bookings: BookingRepository, *reservas: Booking) -> None:
        for r in reservas:
            bookings.add(r)

    # --- add, update e find_by_id --------------------------------------------------------------

    def test_reserva_adicionada_pode_ser_encontrada(self, bookings: BookingRepository) -> None:
        guardada = reserva(intervalo(QUINTA, 14, 16))
        self.povoar(bookings, guardada)
        assert bookings.find_by_id(guardada.id) == guardada

    def test_a_reserva_volta_com_todos_os_campos(self, bookings: BookingRepository) -> None:
        """Ida e volta campo a campo, inclusive a trilha de decisão — um campo esquecido no mapper
        quebra aqui, e não três tasks depois."""
        decidida = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.REJECTED)
        decidida.decided_by = "1998007766"
        decidida.decided_at = datetime(2026, 8, 6, 10, 30)
        decidida.rejection_reason = "O espaço estará em manutenção."
        self.povoar(bookings, decidida)

        assert bookings.find_by_id(decidida.id) == decidida

    def test_buscar_identificador_inexistente_devolve_nulo(
        self, bookings: BookingRepository
    ) -> None:
        """A interface devolve `Booking | None`; quem levanta `BookingNotFound` é o caso de uso."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16)))
        assert bookings.find_by_id(uuid4()) is None

    def test_update_substitui_a_reserva_guardada(self, bookings: BookingRepository) -> None:
        """É como a task 09 persiste uma transição: transiciona a entidade e manda de volta."""
        guardada = reserva(intervalo(QUINTA, 14, 16), status=BookingStatus.PENDING)
        self.povoar(bookings, guardada)

        guardada.status = BookingStatus.APPROVED
        guardada.decided_by = "1998007766"
        guardada.decided_at = datetime(2026, 8, 6, 10, 30)
        bookings.update(guardada)

        encontrada = bookings.find_by_id(guardada.id)
        assert encontrada is not None
        assert (encontrada.status, encontrada.decided_by) == (
            BookingStatus.APPROVED,
            "1998007766",
        )

    def test_update_nao_cria_reserva_nova(self, bookings: BookingRepository) -> None:
        guardada = reserva(intervalo(QUINTA, 14, 16))
        self.povoar(bookings, guardada)
        bookings.update(guardada)
        assert len(bookings.list_by_space_and_date(ESPACO, QUINTA)) == 1

    # --- find_active_overlapping — RN-01 e RN-02 -----------------------------------------------

    def test_sobreposicao_encontra_a_reserva_conflitante(
        self, bookings: BookingRepository
    ) -> None:
        """RN-02."""
        ocupada = reserva(intervalo(QUINTA, 14, 16))
        self.povoar(bookings, ocupada)
        encontradas = bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 15, 17))
        assert ids(encontradas) == {ocupada.id}

    def test_a_reserva_que_termina_quando_o_pedido_comeca_nao_conflita(
        self, bookings: BookingRepository
    ) -> None:
        """RN-02 — uma reserva das 8h às 10h convive com um pedido das 10h às 12h."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 8, 10)))
        assert bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 10, 12)) == []

    def test_a_reserva_que_comeca_quando_o_pedido_termina_nao_conflita(
        self, bookings: BookingRepository
    ) -> None:
        """RN-02 pelo outro lado — e o lado que quase não se testa.

        A fórmula tem duas desigualdades, e cada uma governa uma das bordas. O caso anterior falha
        pela segunda; este falha pela primeira. Testar só um dos dois deixa metade da fórmula sem
        cobertura: trocar a desigualdade que sobra por `<=` cria conflito onde a regra não vê
        nenhum, e nada acusa. Foi um teste de mutação que apontou esta lacuna.
        """
        self.povoar(bookings, reserva(intervalo(QUINTA, 10, 12)))
        assert bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 8, 10)) == []

    def test_um_minuto_de_invasao_ja_e_conflito(self, bookings: BookingRepository) -> None:
        """Do outro lado da mesma borda: encostar não conflita, invadir conflita."""
        ocupada = reserva(TimeSlot(datetime(2026, 8, 20, 9, 59), datetime(2026, 8, 20, 12, 0)))
        self.povoar(bookings, ocupada)
        encontradas = bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 8, 10))
        assert ids(encontradas) == {ocupada.id}

    def test_intervalo_contido_em_outro_conflita(self, bookings: BookingRepository) -> None:
        """RN-02 — a fórmula é simétrica, e contido é caso de sobreposição como qualquer outro."""
        ocupada = reserva(intervalo(QUINTA, 8, 18))
        self.povoar(bookings, ocupada)
        encontradas = bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 10, 12))
        assert ids(encontradas) == {ocupada.id}

    @pytest.mark.parametrize("status", ATIVOS, ids=lambda s: str(s))
    def test_reserva_ativa_ocupa_o_intervalo(
        self, bookings: BookingRepository, status: BookingStatus
    ) -> None:
        """RN-01 — ativa é `PENDING` ou `APPROVED`."""
        ocupada = reserva(intervalo(QUINTA, 14, 16), status=status)
        self.povoar(bookings, ocupada)
        encontradas = bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 14, 16))
        assert ids(encontradas) == {ocupada.id}

    @pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
    def test_reserva_em_estado_terminal_libera_o_intervalo(
        self, bookings: BookingRepository, status: BookingStatus
    ) -> None:
        """RN-01 — uma reserva cancelada devolve o horário para novas solicitações."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16), status=status))
        assert bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 14, 16)) == []

    def test_sobreposicao_e_por_espaco(self, bookings: BookingRepository) -> None:
        """Dois espaços diferentes no mesmo horário não conflitam entre si."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16), space_code=OUTRO_ESPACO))
        assert bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 14, 16)) == []

    def test_espaco_sem_reserva_alguma_nao_conflita(self, bookings: BookingRepository) -> None:
        assert bookings.find_active_overlapping(ESPACO, intervalo(QUINTA, 14, 16)) == []

    # --- find_active_by_requester_in_week — RN-08 ----------------------------------------------

    def test_reservas_da_semana_do_solicitante(self, bookings: BookingRepository) -> None:
        """RN-08 — a semana ISO de referência, e só as do próprio solicitante."""
        minha = reserva(intervalo(QUINTA, 14, 16))
        self.povoar(bookings, minha, reserva(intervalo(QUINTA, 8, 10), requester_id=OUTRO))
        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {minha.id}

    def test_a_semana_comeca_na_segunda(self, bookings: BookingRepository) -> None:
        """A fronteira de trás: domingo anterior está fora, segunda está dentro."""
        na_segunda = reserva(intervalo(date(2026, 8, 17), 8, 10))
        no_domingo_anterior = reserva(intervalo(date(2026, 8, 16), 8, 10))
        self.povoar(bookings, na_segunda, no_domingo_anterior)

        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {na_segunda.id}

    def test_domingo_ainda_esta_na_semana_e_a_segunda_seguinte_nao(
        self, bookings: BookingRepository
    ) -> None:
        """RN-08 — a semana ISO vai de segunda a domingo; a fronteira é entre os dois."""
        no_domingo = reserva(intervalo(DOMINGO, 14, 16))
        na_semana_seguinte = reserva(intervalo(SEGUNDA_SEGUINTE, 14, 16))
        self.povoar(bookings, no_domingo, na_semana_seguinte)

        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {no_domingo.id}

    def test_a_segunda_seguinte_a_meia_noite_ja_e_outra_semana(
        self, bookings: BookingRepository
    ) -> None:
        """A fronteira exata entre duas semanas ISO.

        O teste anterior usa uma reserva às 14h de segunda, o que a deixa longe do limite: qualquer
        comparação razoável a exclui. Só uma reserva começando às 00:00 em ponto distingue um limite
        aberto de um fechado — e é aí que mora a diferença entre contar e não contar as horas dela
        no teto da semana errada.
        """
        na_virada = reserva(TimeSlot(datetime(2026, 8, 24, 0), datetime(2026, 8, 24, 2)))
        self.povoar(bookings, na_virada)
        assert bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA) == []

    def test_a_segunda_da_propria_semana_a_meia_noite_esta_dentro(
        self, bookings: BookingRepository
    ) -> None:
        """E o limite inferior, que é fechado: 00:00 de segunda é o primeiro instante da semana."""
        na_abertura = reserva(TimeSlot(datetime(2026, 8, 17, 0), datetime(2026, 8, 17, 2)))
        self.povoar(bookings, na_abertura)
        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {na_abertura.id}

    def test_a_semana_e_a_do_inicio_da_reserva(self, bookings: BookingRepository) -> None:
        """Uma reserva que atravessa a virada pertence à semana em que começa — é o que a RN-08 diz
        ao contar "reservas cuja data de início cai na mesma semana"."""
        virando_a_semana = reserva(
            TimeSlot(datetime(2026, 8, 23, 22), datetime(2026, 8, 24, 2))
        )
        self.povoar(bookings, virando_a_semana)

        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {virando_a_semana.id}

    @pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
    def test_reserva_inativa_nao_conta_na_semana(
        self, bookings: BookingRepository, status: BookingStatus
    ) -> None:
        """RN-08 — só reservas ativas consomem o teto semanal."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16), status=status))
        assert bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA) == []

    def test_semana_sem_reserva_devolve_lista_vazia(self, bookings: BookingRepository) -> None:
        self.povoar(bookings, reserva(intervalo(SEGUNDA_SEGUINTE, 14, 16)))
        assert bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA) == []

    def test_a_semana_ignora_o_espaco(self, bookings: BookingRepository) -> None:
        """A consulta é por solicitante, não por espaço. O filtro por tipo é do caso de uso (UC-04)."""
        aqui = reserva(intervalo(QUINTA, 8, 10), space_code=ESPACO)
        ali = reserva(intervalo(QUINTA, 14, 16), space_code=OUTRO_ESPACO)
        self.povoar(bookings, aqui, ali)

        encontradas = bookings.find_active_by_requester_in_week(SOLICITANTE, MEIO_DA_QUINTA)
        assert ids(encontradas) == {aqui.id, ali.id}

    # --- list_by_space_and_date — UC-03 --------------------------------------------------------

    def test_agenda_do_dia_traz_as_reservas_ativas_do_espaco(
        self, bookings: BookingRepository
    ) -> None:
        manha = reserva(intervalo(QUINTA, 8, 10))
        tarde = reserva(intervalo(QUINTA, 14, 16))
        self.povoar(
            bookings, manha, tarde, reserva(intervalo(QUINTA, 9, 11), space_code=OUTRO_ESPACO)
        )
        assert ids(bookings.list_by_space_and_date(ESPACO, QUINTA)) == {manha.id, tarde.id}

    @pytest.mark.parametrize("status", INATIVOS, ids=lambda s: str(s))
    def test_agenda_do_dia_ignora_reserva_em_estado_terminal(
        self, bookings: BookingRepository, status: BookingStatus
    ) -> None:
        """UC-03 — canceladas e rejeitadas não aparecem: o horário está livre."""
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16), status=status))
        assert bookings.list_by_space_and_date(ESPACO, QUINTA) == []

    def test_agenda_do_dia_ignora_outro_dia(self, bookings: BookingRepository) -> None:
        self.povoar(bookings, reserva(intervalo(QUINTA, 14, 16)))
        assert bookings.list_by_space_and_date(ESPACO, DOMINGO) == []

    def test_reserva_que_atravessa_a_meia_noite_aparece_nos_dois_dias(
        self, bookings: BookingRepository
    ) -> None:
        """UC-03 serve para achar as faixas livres: uma reserva das 22h às 2h ocupa as duas manhãs."""
        virada = reserva(TimeSlot(datetime(2026, 8, 20, 22), datetime(2026, 8, 21, 2)))
        self.povoar(bookings, virada)
        assert ids(bookings.list_by_space_and_date(ESPACO, QUINTA)) == {virada.id}
        assert ids(bookings.list_by_space_and_date(ESPACO, SEXTA)) == {virada.id}

    def test_reserva_que_termina_a_meia_noite_nao_invade_o_dia_seguinte(
        self, bookings: BookingRepository
    ) -> None:
        """A fronteira é a mesma da RN-02: tocar a borda não é ocupar."""
        ate_meia_noite = reserva(TimeSlot(datetime(2026, 8, 20, 22), datetime(2026, 8, 21, 0)))
        self.povoar(bookings, ate_meia_noite)
        assert ids(bookings.list_by_space_and_date(ESPACO, QUINTA)) == {ate_meia_noite.id}
        assert bookings.list_by_space_and_date(ESPACO, SEXTA) == []

    def test_reserva_que_comeca_a_meia_noite_nao_aparece_no_dia_anterior(
        self, bookings: BookingRepository
    ) -> None:
        """A outra ponta do mesmo dia, e a que o teste acima não alcança.

        O dia é um intervalo fechado no início e aberto no fim. Uma reserva que começa exatamente
        na meia-noite seguinte pertence ao dia seguinte e a nenhum pedaço deste — e é o caso que
        distingue `<` de `<=` no limite superior da consulta.
        """
        madrugada = reserva(TimeSlot(datetime(2026, 8, 21, 0), datetime(2026, 8, 21, 2)))
        self.povoar(bookings, madrugada)
        assert bookings.list_by_space_and_date(ESPACO, QUINTA) == []
        assert ids(bookings.list_by_space_and_date(ESPACO, SEXTA)) == {madrugada.id}

    def test_dia_sem_reserva_devolve_lista_vazia(self, bookings: BookingRepository) -> None:
        assert bookings.list_by_space_and_date(ESPACO, QUINTA) == []
