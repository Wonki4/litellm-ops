from sqlalchemy.orm import DeclarativeBase


class CustomBase(DeclarativeBase):
    """Base class for all custom tables. Uses 'custom_' prefix convention."""

    pass
