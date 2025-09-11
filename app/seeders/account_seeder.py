"""
Account seeder to create default accounts for existing users.
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import User, Account


def seed_default_accounts():
    """Create default savings accounts for users who don't have any."""
    db: Session = SessionLocal()
    
    try:
        print("🌱 Starting account seeding...")
        
        # Get all users who don't have any accounts
        users_without_accounts = (
            db.query(User)
            .outerjoin(Account, User.id == Account.user_id)
            .filter(Account.id.is_(None))
            .all()
        )
        
        print(f"Found {len(users_without_accounts)} users without accounts")
        
        created_accounts = []
        
        for user in users_without_accounts:
            # Extract number from customer_id (CUST-000001 -> 000001)
            customer_number = user.customer_id.split('-')[1]
            account_number = f"ACC{customer_number}001"
            
            # Create default savings account
            default_account = Account(
                user_id=user.id,
                account_number=account_number,
                account_type="savings",
                balance=0.00,
                currency="IDR",
                status="active"
            )
            
            db.add(default_account)
            created_accounts.append({
                "user": user.username,
                "customer_id": user.customer_id,
                "account_number": account_number
            })
            
            print(f"✅ Created account {account_number} for user {user.username} ({user.customer_id})")
        
        # Commit all changes
        db.commit()
        
        print(f"\n🎉 Successfully created {len(created_accounts)} default accounts!")
        print("\nSummary:")
        for acc in created_accounts:
            print(f"  - {acc['user']} ({acc['customer_id']}) → {acc['account_number']}")
            
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def seed_sample_balances():
    """Add sample balances to existing accounts for testing."""
    db: Session = SessionLocal()
    
    try:
        print("💰 Adding sample balances...")
        
        accounts = db.query(Account).filter(Account.status == "active").all()
        
        # Sample balances
        sample_balances = [1000000.00, 500000.00, 2500000.00, 750000.00, 1500000.00]
        
        for i, account in enumerate(accounts):
            balance = sample_balances[i % len(sample_balances)]
            account.balance = balance
            print(f"💳 Set balance {balance:,.2f} IDR for account {account.account_number}")
        
        db.commit()
        print(f"✅ Updated balances for {len(accounts)} accounts")
        
    except Exception as e:
        print(f"❌ Error adding balances: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Running Account Seeder...")
    seed_default_accounts()
    
    # Optionally add sample balances
    add_balances = input("\n💰 Add sample balances to accounts? (y/N): ").lower().strip()
    if add_balances == 'y':
        seed_sample_balances()
    
    print("\n✨ Account seeding completed!")