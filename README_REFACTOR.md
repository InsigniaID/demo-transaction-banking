# Code Structure Refactor

This document explains the new organized code structure.

## New Structure

```
app/
├── __init__.py
├── main.py                 # Clean FastAPI app initialization
├── main_old.py            # Backup of original main.py
├── auth.py                # Authentication utilities
├── database.py            # Database configuration
├── kafka_producer.py      # Kafka producer
├── models.py              # SQLAlchemy models
├── schemas.py             # Pydantic schemas
├── security.py            # Security utilities
├── api/                   # API layer
│   ├── __init__.py
│   ├── deps.py           # Common dependencies
│   └── v1/               # API version 1
│       ├── __init__.py
│       ├── api.py        # Main API router
│       ├── auth.py       # Authentication endpoints
│       └── transactions.py # Transaction endpoints
├── core/                  # Core configuration
│   ├── __init__.py
│   └── config.py         # Settings and configuration
├── services/             # Business logic layer
│   ├── __init__.py
│   ├── auth_service.py   # Authentication business logic
│   ├── qris_service.py   # QRIS payment logic
│   └── transaction_service.py # Transaction processing
└── utils/                # Utility functions
    ├── __init__.py
    └── qris.py           # QRIS encoding/decoding utilities
```

## Key Improvements

### 1. Separation of Concerns
- **API Layer**: Clean endpoint definitions in `/api/v1/`
- **Business Logic**: Moved to `/services/`
- **Utilities**: Common functions in `/utils/`
- **Configuration**: Centralized in `/core/config.py`

### 2. Configuration Management
- Uses `pydantic-settings` for type-safe configuration
- All environment variables managed in one place
- Easy to mock for testing

### 3. Service Layer
- **AuthService**: Handles login attempts and security alerts
- **QRISService**: QRIS generation and validation
- **TransactionService**: Transaction data creation and Kafka publishing

### 4. Clean API Structure
- Versioned APIs (`/api/v1/`)
- Grouped endpoints by functionality
- Reusable dependencies in `deps.py`

### 5. Improved Maintainability
- Single responsibility principle
- Easy to test individual components
- Clear import paths
- Reduced coupling between components

## Migration Notes

### Breaking Changes
- API endpoints now have `/api/v1/` prefix
- Some internal imports have changed

### Compatibility
- All existing functionality is preserved
- Old `main.py` is backed up as `main_old.py`

## Usage

The new structure maintains all existing endpoints but with better organization:

- `POST /api/v1/users/` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/transaction/retail/qris-generate` - Generate QRIS
- `POST /api/v1/transaction/retail/qris-consume` - Consume QRIS
- `POST /api/v1/transaction/corporate` - Corporate transactions

## Development

Use the existing Makefile commands:
- `make install` - Install dependencies
- `make dev` - Run development server
- `make docker-run` - Run with Docker