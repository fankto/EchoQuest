from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
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
        return transaction
    
    async def get_user_transactions(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        transaction_type: Optional[TransactionType] = None,
    ) -> List[Transaction]:
        """Get user transactions"""
        query = select(Transaction).filter(Transaction.user_id == user_id)
        
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
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
    
    async def get_interview_transactions(
        self,
        db: AsyncSession,
        *,
        interview_id: UUID,
        skip: int = 0,
        limit: int = 100,
        transaction_type: Optional[TransactionType] = None,
    ) -> List[Transaction]:
        """Get interview transactions"""
        query = select(Transaction).filter(Transaction.interview_id == interview_id)
        
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()


transaction_crud = CRUDTransaction(Transaction)