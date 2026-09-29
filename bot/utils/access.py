from bot.config import settings
from bot.db.models import User


def has_access(user: User) -> bool:
    """Verified students and configured admins can open locked material."""
    return user.is_verified or user.telegram_id in settings.admin_id_set
