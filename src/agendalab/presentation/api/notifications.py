"""`GET /notifications` e `GET /health`.

A caixa de entrada é a **evidência visível do padrão Observer** (ADR-0006). Sem esta rota, a única
prova de que o padrão funciona estaria no log do servidor, e a defesa precisaria pedir que se
acreditasse nela. Com ela, a relação de causa e efeito é demonstrável numa captura de tela: aprovar
uma reserva, consultar a caixa, ver a notificação.

Ela vive em memória e se perde no reinício, de propósito — é instrumento de demonstração, não
funcionalidade de produto.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agendalab.presentation.api.schemas import NotificationResponse
from agendalab.presentation.dependencies import InboxDep, get_actor

router = APIRouter(tags=["operação"])


@router.get(
    "/notifications",
    summary="Consultar a caixa de notificações",
    response_description="As notificações produzidas, da mais antiga para a mais recente",
    dependencies=[Depends(get_actor)],
)
def list_notifications(inbox: InboxDep) -> list[NotificationResponse]:
    """Nenhum caso de uso no caminho, e é correto: não há operação de negócio aqui.

    A caixa é infraestrutura de notificação sendo lida diretamente, não estado do sistema — as
    reservas continuam vindo por `/bookings`.
    """
    return [NotificationResponse.of(n) for n in inbox.all()]


@router.get("/health", summary="Verificação operacional")
def health() -> dict[str, str]:
    """Responde sem tocar banco e **sem exigir identidade**.

    É a única rota assim, e de propósito: quem chama uma verificação de saúde é um orquestrador ou
    um balanceador, que não tem identidade para declarar. O que se pergunta aqui é se o processo
    está de pé, e a resposta não expõe dado algum.
    """
    return {"status": "ok"}
