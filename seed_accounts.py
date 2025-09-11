#!/usr/bin/env python3
"""
Run account seeder to create default accounts for existing users.
"""
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.seeders.account_seeder import seed_default_accounts, seed_sample_balances


def main():
    """Main seeder function."""
    print("🚀 Account Seeder - Creating default accounts for existing users")
    print("=" * 60)
    
    try:
        # Create default accounts
        seed_default_accounts()
        
        # Ask if user wants to add sample balances
        print("\n" + "=" * 60)
        choice = input("💰 Would you like to add sample balances for testing? (y/N): ").lower().strip()
        
        if choice in ['y', 'yes']:
            seed_sample_balances()
        
        print("\n🎉 Account seeding completed successfully!")
        print("Users can now use QRIS and other transaction features.")
        
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()