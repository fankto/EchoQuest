import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.crud.crud_transaction import transaction_crud
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import TransactionType, User
from app.schemas.credit import (
    CreditPackage,
    CreditPurchase,
    CreditPurchaseResponse,
    TokenPackage,
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
                description=f"{package_data['tokens']/1000:.0f}K chat tokens",
            )
        )
    
    return packages


@router.post("/purchase-credits", response_model=CreditPurchaseResponse)
async def purchase_interview_credits(
    purchase: CreditPurchase,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Purchase interview credits.
    
    This is a simplified endpoint for demonstration purposes.
    In a production environment, this would integrate with a payment processor
    such as Stripe or PayPal.
    """
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
            interview_id=None,
            transaction_type=TransactionType.INTERVIEW_CREDIT_PURCHASE,
            amount=package.credits,
            price=package.price,
            reference=str(uuid.uuid4()),  # Generate a reference/invoice number
        )
        
        await db.commit()
        
        # Return response
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
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Purchase chat tokens.
    
    This is a simplified endpoint for demonstration purposes.
    In a production environment, this would integrate with a payment processor
    such as Stripe or PayPal.
    """
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
            interview_id=None,
            transaction_type=TransactionType.CHAT_TOKEN_PURCHASE,
            amount=tokens,
            price=price,
            reference=str(uuid.uuid4()),  # Generate a reference/invoice number
        )
        
        await db.commit()
        
        # Return response
        return CreditPurchaseResponse(
            success=True,
            message=f"Successfully purchased {tokens/1000:.0f}K chat tokens",
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