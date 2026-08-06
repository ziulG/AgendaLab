"""As tabelas — deliberadamente separadas das entidades de domínio.

Duas famílias de classes descrevendo as mesmas coisas é o custo direto do ADR-0003, aceito de olhos
abertos. O que se compra com ele: `Space` e `Booking` não sabem que SQLAlchemy existe, e o esquema
físico pode divergir do modelo de domínio sem que nenhum dos dois lados ceda.

A divergência mais visível está aqui: `TimeSlot` é um objeto de valor no domínio e **duas colunas**
nesta tabela. Nem o domínio precisou achatar o intervalo em dois campos soltos, nem o banco precisou
de um tipo composto.

As colunas de enumeração guardam **texto**, não o enum. A conversão é do mapper, num lugar só —
manter o modelo em tipos primitivos é o que impede que uma renomeação no domínio vire migração de
esquema silenciosa.

Fiel ao diagrama ER da ARQUITETURA §10. Não há tabela de usuários: `requester_id` e `decided_by` são
identificadores opacos, sem integridade referencial, porque não existe entidade para referenciar
(ADR-0007).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from agendalab.infrastructure.persistence.database import Base


class SpaceModel(Base):
    __tablename__ = "spaces"

    # Chave natural, e não um inteiro sequencial: é o que torna as rotas legíveis
    # (`/spaces/LAB-01/availability`). O custo — renomear um código sai caro — está assumido no
    # ADR-0003, que declara o código imutável.
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BookingModel(Base):
    __tablename__ = "bookings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    space_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("spaces.code"), nullable=False, index=True
    )
    requester_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # O `TimeSlot` do domínio, achatado. `start_at` é indexado porque as três consultas do
    # repositório filtram por ele — sobreposição, semana e agenda do dia.
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    attendees: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Trilha de decisão — nula até que alguém decida sobre a reserva.
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
