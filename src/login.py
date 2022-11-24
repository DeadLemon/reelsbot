import enum

from instaloader import (
    BadCredentialsException,
    ConnectionException,
    Instaloader,
    InvalidArgumentException,
    TwoFactorAuthRequiredException,
)
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.loader import (
    get_instagram_loader,
    get_instagram_username,
    set_instagram_loader,
    set_instagram_username,
)


class Login(enum.Enum):
    USERNAME = 1
    PASSWORD = 2
    TWO_FACTOR = 3


def make_login_conversation_handler() -> ConversationHandler:
    login_abort = CommandHandler(
        'login_abort',
        callback=login_abort_handler,
        filters=filters.ChatType.PRIVATE
    )

    return ConversationHandler(
        entry_points=[
            CommandHandler(
                command='start',
                callback=login_command_handler,
                filters=filters.ChatType.PRIVATE,
            ),
            CommandHandler(
                command='login',
                callback=login_command_handler,
                filters=filters.ChatType.PRIVATE,
            ),
        ],
        states={
            Login.USERNAME: [
                login_abort,
                MessageHandler(filters.TEXT, login_username_message_handler),
            ],
            Login.PASSWORD: [
                login_abort,
                MessageHandler(filters.TEXT, login_password_message_handler),
            ],
            Login.TWO_FACTOR: [
                login_abort,
                MessageHandler(
                    filters.ChatType.PRIVATE & filters.TEXT,
                    login_two_factor_auth_code_handler,
                ),
            ]
        },
        fallbacks=[
            MessageHandler(
                filters.ChatType.PRIVATE,
                login_fallback_handler,
            ),
        ]
    )


async def login_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loader_ = get_instagram_loader(context)
    if not loader_:
        loader_ = Instaloader(max_connection_attempts=1)
        set_instagram_loader(context, loader_)

    username = None
    try:
        username = loader_.test_login()
    except ConnectionException:
        ...

    if username:
        await update.message.reply_text('already logged in')
        return ConversationHandler.END

    await update.message.reply_text('enter instagram username')
    return Login.USERNAME


async def login_username_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loader_ = get_instagram_loader(context)
    if not loader_:
        return ConversationHandler.END

    username = update.message.text
    if not username:
        return ConversationHandler.END

    try:
        loader_.load_session_from_file(username)
    except FileNotFoundError:
        ...

    test_username = None
    try:
        test_username = loader_.test_login()
    except ConnectionException:
        ...

    if test_username:
        await update.message.reply_text('already logged in')
        return ConversationHandler.END

    set_instagram_username(context, username)
    await update.message.reply_text('enter instagram password')
    return Login.PASSWORD


async def login_password_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loader_ = get_instagram_loader(context)
    if not loader_:
        return ConversationHandler.END

    username = get_instagram_username(context)
    if not username:
        return ConversationHandler.END

    password = update.message.text
    if not password:
        return ConversationHandler.END

    await update.message.edit_text('**********')

    try:
        loader_.login(username, password)
    except InvalidArgumentException:
        await update.message.reply_text('wrong username, try again')
        return Login.USERNAME
    except BadCredentialsException:
        await update.message.reply_text('wrong password, try again')
        return Login.PASSWORD
    except ConnectionException:
        await update.message.reply_text('connection failed, try again')
        return ConversationHandler.END
    except TwoFactorAuthRequiredException:
        await update.message.reply_text('enter instagram 2fa code')
        return Login.TWO_FACTOR

    return ConversationHandler.END


async def login_two_factor_auth_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loader_ = get_instagram_loader(context)
    if not loader_:
        return ConversationHandler.END

    two_factor_code = update.message.text
    if not two_factor_code:
        return ConversationHandler.END

    loader_.two_factor_login(two_factor_code)
    return ConversationHandler.END


async def login_abort_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.delete()
    return ConversationHandler.END


async def login_fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Login process terminated')
    return ConversationHandler.END
