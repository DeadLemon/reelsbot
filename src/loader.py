from typing import Optional

from instaloader import Instaloader
from telegram.ext import ContextTypes


def get_instagram_username(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    return context.user_data.get('instagram_username', None)


def set_instagram_username(context: ContextTypes.DEFAULT_TYPE, instagram_username: str) -> None:
    return context.user_data.update(
        {
            'instagram_username': instagram_username,
        }
    )


def get_instagram_loader(context: ContextTypes.DEFAULT_TYPE) -> Optional[Instaloader]:
    return context.user_data.get('instagram_loader', None)


def set_instagram_loader(context: ContextTypes.DEFAULT_TYPE, instagram_loader: Optional[Instaloader]) -> None:
    return context.user_data.update(
        {
            'instagram_loader': instagram_loader,
        }
    )
