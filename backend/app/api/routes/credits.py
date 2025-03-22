import uuid
from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, validate_organization_admin
from app.core.config import settings
from app.crud.crud_transaction import transaction_crud
from app.crud.crud_user import user_crud
from app.crud.crud_organization import organization_crud
from app.db.session import get_db
from app.models.models import TransactionType, User
from app.schemas.credit import (
    CreditPackage,
    CreditPurchase,
    CreditPurchaseResponse,
    CreditSummary,
    TokenPackage,
    TransactionResponse,
    TransactionSummary,
)

router = APIRouter()


@router.get("/interview-packages", response_model=List[CreditPackage])
async def get_interview_credit_packages() -> Any:
    """
    Get available interview credit packages.
    """
    # Define standard packages
    packages = [
        CreditPackage(
            id="starter",
            name="Starter Pack",
            credits=10,
            price=49.00,
            description="10 interview credits (~$4.90/interview)",
            validity_days=365,
        ),
        CreditPackage(
            id="professional",
            name="Professional Bundle",
            credits=40,
            price=149.00,
            description="40 interview credits (~$3.73/interview)",
            validity_days=365,
        ),
        CreditPackage(
            id="team",
            name="Team Bundle",
            credits=100,
            price=349.00,
            description="100 interview credits (~$3.49/interview)",
            validity_days=547,  # 18 months
        ),
    ]

    return packages


@router.get("/token-packages", response_model=List[TokenPackage])
async def get_chat_token_packages() -> Any:
    """
    Get available chat token packages.
    """
    # Define standard packages from settings
    packages = []

    for package_id, package_data in settings.CHAT_TOKEN_PACKAGES.items():
        packages.append(
            TokenPackage(
                id=package_id,
                name=f"{package_id.capitalize()} Token Package",
                tokens=package_data["tokens"],
                price=package_data["price"],
                description=f"{package_data['tokens'] / 1000:.0f}K chat tokens",
            )
        )

    return packages


@router.post("/purchase-credits", response_model=CreditPurchaseResponse)
async def purchase_interview_credits(
        purchase: CreditPurchase,
        current_user: User = Depends(get_current_active_user),
        organization_id: Optional[uuid.UUID] = Query(None,
                                                     description="Optional organization ID for organization purchase"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Purchase interview credits.

    This is a simplified endpoint for demonstration purposes.
    In a production environment, this would integrate with a payment processor
    such as Stripe or PayPal.
    """
    # Check organization permissions if specified
    organization = None
    if organization_id:
        organization = await validate_organization_admin(db, organization_id, current_user.id)

    # Get the package
    packages = await get_interview_credit_packages()
    package = next((p for p in packages if p.id == purchase.package_id), None)

    if not package:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid package ID: {purchase.package_id}",
        )

    try:
        # In a real implementation, we would process payment here
        # For demonstration, we'll just add the credits

        reference = str(uuid.uuid4())  # Generate a reference/invoice number

        if organization_id:
            # Add credits to organization
            org = await organization_crud.add_credits(
                db=db,
                organization_id=organization_id,
                credits=package.credits,
            )

            # Create transaction record
            transaction = await transaction_crud.create_transaction(
                db=db,
                user_id=current_user.id,
                organization_id=organization_id,
                transaction_type=TransactionType.INTERVIEW_CREDIT_PURCHASE,
                amount=package.credits,
                price=package.price,
                reference=reference,
            )

            await db.commit()

            return CreditPurchaseResponse(
                success=True,
                message=f"Successfully purchased {package.credits} interview credits for your organization",
                credits_added=package.credits,
                total_credits=org.available_interview_credits,
                transaction_id=str(transaction.id),
            )
        else:
            # Add credits to user
            user = await user_crud.add_credits(
                db=db,
                user_id=current_user.id,
                credits=package.credits,
            )

            # Create transaction record
            transaction = await transaction_crud.create_transaction(
                db=db,
                user_id=current_user.id,
                organization_id=None,  # Personal purchase
                transaction_type=TransactionType.INTERVIEW_CREDIT_PURCHASE,
                amount=package.credits,
                price=package.price,
                reference=reference,
            )

            await db.commit()

            return CreditPurchaseResponse(
                success=True,
                message=f"Successfully purchased {package.credits} interview credits",
                credits_added=package.credits,
                total_credits=user.available_interview_credits,
                transaction_id=str(transaction.id),
            )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process purchase: {str(e)}",
        )


@router.post("/purchase-tokens", response_model=CreditPurchaseResponse)
async def purchase_chat_tokens(
        purchase: CreditPurchase,
        current_user: User = Depends(get_current_active_user),
        organization_id: Optional[uuid.UUID] = Query(None,
                                                     description="Optional organization ID for organization purchase"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Purchase chat tokens.

    This is a simplified endpoint for demonstration purposes.
    In a production environment, this would integrate with a payment processor
    such as Stripe or PayPal.
    """
    # Check organization permissions if specified
    organization = None
    if organization_id:
        organization = await validate_organization_admin(db, organization_id, current_user.id)

    # Get the package
    if purchase.package_id not in settings.CHAT_TOKEN_PACKAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid package ID: {purchase.package_id}",
        )

    package_data = settings.CHAT_TOKEN_PACKAGES[purchase.package_id]
    tokens = package_data["tokens"]
    price = package_data["price"]

    try:
        # In a real implementation, we would process payment here
        # For demonstration, we'll just add the tokens

        reference = str(uuid.uuid4())  # Generate a reference/invoice number

        if organization_id:
            # Add tokens to organization
            org = await organization_crud.add_chat_tokens(
                db=db,
                organization_id=organization_id,
                tokens=tokens,
            )

            # Create transaction record
            transaction = await transaction_crud.create_transaction(
                db=db,
                user_id=current_user.id,
                organization_id=organization_id,
                transaction_type=TransactionType.CHAT_TOKEN_PURCHASE,
                amount=tokens,
                price=price,
                reference=reference,
            )

            await db.commit()

            return CreditPurchaseResponse(
                success=True,
                message=f"Successfully purchased {tokens / 1000:.0f}K chat tokens for your organization",
                credits_added=tokens,
                total_credits=org.available_chat_tokens,
                transaction_id=str(transaction.id),
            )
        else:
            # Add tokens to user
            user = await user_crud.add_chat_tokens(
                db=db,
                user_id=current_user.id,
                tokens=tokens,
            )

            # Create transaction record
            transaction = await transaction_crud.create_transaction(
                db=db,
                user_id=current_user.id,
                organization_id=None,  # Personal purchase
                transaction_type=TransactionType.CHAT_TOKEN_PURCHASE,
                amount=tokens,
                price=price,
                reference=reference,
            )

            await db.commit()

            return CreditPurchaseResponse(
                success=True,
                message=f"Successfully purchased {tokens / 1000:.0f}K chat tokens",
                credits_added=tokens,
                total_credits=user.available_chat_tokens,
                transaction_id=str(transaction.id),
            )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process purchase: {str(e)}",
        )


@router.get("/summary", response_model=CreditSummary)
async def get_credit_summary(
        current_user: User = Depends(get_current_active_user),
        organization_id: Optional[uuid.UUID] = Query(None,
                                                     description="Optional organization ID for organization credits"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get credit summary for the current user or specified organization.
    """
    # If organization ID is provided, get organization credits
    if organization_id:
        # Check if user is a member of the organization
        is_member = await organization_crud.is_user_in_org(db, organization_id=organization_id, user_id=current_user.id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

        # Get organization
        organization = await organization_crud.get(db, id=organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        # Get interview credits used
        interview_credits_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.INTERVIEW_CREDIT_USAGE.value}'"
        )
        credits_used = interview_credits_used.scalar_one() or 0

        # Get chat tokens used
        chat_tokens_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.CHAT_TOKEN_USAGE.value}'"
        )
        tokens_used = chat_tokens_used.scalar_one() or 0

        return CreditSummary(
            available_interview_credits=organization.available_interview_credits,
            available_chat_tokens=organization.available_chat_tokens,
            interview_credits_used=credits_used,
            chat_tokens_used=tokens_used,
        )
    else:
        # Get personal credits

        # Get interview credits used
        interview_credits_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = '{current_user.id}' AND organization_id IS NULL AND transaction_type = '{TransactionType.INTERVIEW_CREDIT_USAGE.value}'"
        )
        credits_used = interview_credits_used.scalar_one() or 0

        # Get chat tokens used
        chat_tokens_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = '{current_user.id}' AND organization_id IS NULL AND transaction_type = '{TransactionType.CHAT_TOKEN_USAGE.value}'"
        )
        tokens_used = chat_tokens_used.scalar_one() or 0

        return CreditSummary(
            available_interview_credits=current_user.available_interview_credits,
            available_chat_tokens=current_user.available_chat_tokens,
            interview_credits_used=credits_used,
            chat_tokens_used=tokens_used,
        )


@router.get("/transactions", response_model=TransactionSummary)
async def get_transaction_summary(
        current_user: User = Depends(get_current_active_user),
        organization_id: Optional[uuid.UUID] = Query(None,
                                                     description="Optional organization ID for organization transactions"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get transaction summary for the current user or specified organization.
    """
    # If organization ID is provided, get organization transactions
    if organization_id:
        # Check organization permissions
        await validate_organization_admin(db, organization_id, current_user.id)

        # Get transaction summary
        transactions = await transaction_crud.get_organization_transactions(
            db,
            organization_id=organization_id,
            limit=10
        )

        # Format transactions
        recent_transactions = [
            TransactionResponse(
                id=t.id,
                transaction_type=t.transaction_type.value,
                amount=t.amount,
                price=t.price,
                reference=t.reference,
                created_at=t.created_at.isoformat(),
                interview_id=t.interview_id,
            )
            for t in transactions
        ]

        # Calculate totals
        interview_credits_purchased = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.INTERVIEW_CREDIT_PURCHASE.value}'"
        )
        total_interview_credits_purchased = interview_credits_purchased.scalar_one() or 0

        interview_credits_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.INTERVIEW_CREDIT_USAGE.value}'"
        )
        total_interview_credits_used = interview_credits_used.scalar_one() or 0

        chat_tokens_purchased = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.CHAT_TOKEN_PURCHASE.value}'"
        )
        total_chat_tokens_purchased = chat_tokens_purchased.scalar_one() or 0

        chat_tokens_used = await db.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE organization_id = '{organization_id}' AND transaction_type = '{TransactionType.CHAT_TOKEN_USAGE.value}'"
        )
        total_chat_tokens_used = chat_tokens_used.scalar_one() or 0

        total_spent = await db.execute(
            f"SELECT COALESCE(SUM(price), 0) FROM transactions WHERE organization_id = '{organization_id}' AND price IS NOT NULL"
        )
        total_spent_amount = total_spent.scalar_one() or 0

        return TransactionSummary(
            total_interview_credits_purchased=total_interview_credits_purchased,
            total_interview_credits_used=total_interview_credits_used,
            total_chat_tokens_purchased=total_chat_tokens_purchased,
            total_chat_tokens_used=total_chat_tokens_used,
            total_spent=total_spent_amount,
            recent_transactions=recent_transactions,
        )
    else:
        # Get personal transaction summary
        summary = await transaction_crud.get_user_transaction_summary(db, user_id=current_user.id)

        # Format transactions
        recent_transactions = [
            TransactionResponse(
                id=t.id,
                transaction_type=t.transaction_type.value,
                amount=t.amount,
                price=t.price,
                reference=t.reference,
                created_at=t.created_at.isoformat(),
                interview_id=t.interview_id,
            )
            for t in summary.get("recent_transactions", [])
        ]

        return TransactionSummary(
            total_interview_credits_purchased=summary.get("total_interview_credits_purchased", 0),
            total_interview_credits_used=summary.get("total_interview_credits_used", 0),
            total_chat_tokens_purchased=summary.get("total_chat_tokens_purchased", 0),
            total_chat_tokens_used=summary.get("total_chat_tokens_used", 0),
            total_spent=summary.get("total_spent", 0),
            recent_transactions=recent_transactions,
        )


@router.get("/transactions/list", response_model=List[TransactionResponse])
async def list_transactions(
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
        date_range: Optional[str] = Query(None, description="Filter by date range (week, month, year)"),
        organization_id: Optional[uuid.UUID] = Query(None,
                                                     description="Optional organization ID for organization transactions"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get paginated transaction list for the current user or specified organization.
    """
    # Calculate skip
    skip = (page - 1) * size

    # Convert transaction type to enum if provided
    tx_type = None
    if transaction_type:
        try:
            tx_type = TransactionType(transaction_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction type: {transaction_type}",
            )

    # If organization ID is provided, get organization transactions
    if organization_id:
        # Check organization permissions
        await validate_organization_admin(db, organization_id, current_user.id)

        # Get transactions
        transactions = await transaction_crud.get_organization_transactions(
            db,
            organization_id=organization_id,
            skip=skip,
            limit=size,
            transaction_type=tx_type
        )
    else:
        # Get personal transactions
        transactions = await transaction_crud.get_user_transactions(
            db,
            user_id=current_user.id,
            skip=skip,
            limit=size,
            transaction_type=tx_type,
            date_range=date_range
        )

    # Format transactions
    return [
        TransactionResponse(
            id=t.id,
            transaction_type=t.transaction_type.value,
            amount=t.amount,
            price=t.price,
            reference=t.reference,
            created_at=t.created_at.isoformat(),
            interview_id=t.interview_id,
        )
        for t in transactions
    ]