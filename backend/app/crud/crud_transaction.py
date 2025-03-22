from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.models import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionUpdate


class CRUDTransaction(CRUDBase[Transaction, TransactionCreate, TransactionUpdate]):
    """CRUD operations for Transaction model"""

    async def create_transaction(
            self,
            db: AsyncSession,
            *,
            user_id: UUID,
            transaction_type: TransactionType,
            amount: int,
            organization_id: Optional[UUID] = None,
            interview_id: Optional[UUID] = None,
            price: Optional[float] = None,
            reference: Optional[str] = None,
    ) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            user_id=user_id,
            organization_id=organization_id,
            interview_id=interview_id,
            transaction_type=transaction_type,
            amount=amount,
            price=price,
            reference=reference,
        )

        db.add(transaction)
        await db.flush()
        await db.refresh(transaction)
        return transaction

    async def get_user_transactions(
            self,
            db: AsyncSession,
            *,
            user_id: UUID,
            skip: int = 0,
            limit: int = 100,
            transaction_type: Optional[TransactionType] = None,
            date_range: Optional[str] = None,
    ) -> List[Transaction]:
        """Get user transactions"""
        query = select(Transaction).filter(Transaction.user_id == user_id)

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        if date_range:
            now = datetime.utcnow()
            if date_range == 'week':
                query = query.filter(Transaction.created_at >= now - timedelta(days=7))
            elif date_range == 'month':
                query = query.filter(Transaction.created_at >= now - timedelta(days=30))
            elif date_range == 'year':
                query = query.filter(Transaction.created_at >= now - timedelta(days=365))

        query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_user_transaction_summary(
            self,
            db: AsyncSession,
            *,
            user_id: UUID,
    ) -> Dict[str, Any]:
        """Get transaction summary for a user"""
        # Get total credits purchased
        interview_credits_purchased = await db.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.INTERVIEW_CREDIT_PURCHASE
            )
        )
        total_interview_credits_purchased = interview_credits_purchased.scalar_one() or 0

        # Get total credits used
        interview_credits_used = await db.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.INTERVIEW_CREDIT_USAGE
            )
        )
        total_interview_credits_used = interview_credits_used.scalar_one() or 0

        # Get total chat tokens purchased
        chat_tokens_purchased = await db.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.CHAT_TOKEN_PURCHASE
            )
        )
        total_chat_tokens_purchased = chat_tokens_purchased.scalar_one() or 0

        # Get total chat tokens used
        chat_tokens_used = await db.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.CHAT_TOKEN_USAGE
            )
        )
        total_chat_tokens_used = chat_tokens_used.scalar_one() or 0

        # Get total spent
        total_spent = await db.execute(
            select(func.sum(Transaction.price))
            .where(
                Transaction.user_id == user_id,
                Transaction.price != None  # noqa
            )
        )
        total_spent_amount = total_spent.scalar_one() or 0

        # Get recent transactions
        recent = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(5)
        )
        recent_transactions = recent.scalars().all()

        return {
            "total_interview_credits_purchased": total_interview_credits_purchased,
            "total_interview_credits_used": total_interview_credits_used,
            "total_chat_tokens_purchased": total_chat_tokens_purchased,
            "total_chat_tokens_used": total_chat_tokens_used,
            "total_spent": total_spent_amount,
            "recent_transactions": recent_transactions,
        }

    async def get_organization_transactions(
            self,
            db: AsyncSession,
            *,
            organization_id: UUID,
            skip: int = 0,
            limit: int = 100,
            transaction_type: Optional[TransactionType] = None,
    ) -> List[Transaction]:
        """Get organization transactions"""
        query = select(Transaction).filter(Transaction.organization_id == organization_id)

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()


transaction_crud = CRUDTransaction(Transaction)