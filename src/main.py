import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import instagrapi as ig
import sentry_sdk as ss
from dotenv import load_dotenv
from sentry_sdk import capture_exception
from telegram import (
    InlineQueryResultVideo,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    InlineQueryHandler,
    PersistenceInput,
    PicklePersistence,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

log = logging.getLogger(__name__)


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if query == '':
        await update.inline_query.answer([], is_personal=True, cache_time=0)
        return

    log.info(
        'inline query received, user_id=%s, username=%s, query=%s',
        update.effective_user.id,
        update.effective_user.username,
        update.inline_query.query,
    )

    try:
        pk = c.media_pk_from_url(query)
        info = c.media_info(pk, use_cache=True)
        # video = c.video_download(pk, folder=downloads_path)
    except Exception as e:
        capture_exception(e)
        log.info(
            'inline query failed, user_id=%s, username=%s, query=%s: %s',
            update.effective_user.id,
            update.effective_user.username,
            update.inline_query.query,
            e,
        )
        await update.inline_query.answer([], is_personal=True, cache_time=0)
        return

    await update.inline_query.answer(
        [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                # video_url='/'.join([bot_url, video.as_posix()]),
                video_url=info.video_url,
                mime_type='video/mp4',
                thumb_url=info.thumbnail_url,
                title=info.title or c.media_code_from_pk(pk),
                # caption=info.caption_text,
                video_duration=int(float(info.video_duration)),
                video_width=1080,
                video_height=1920,
            )
        ],
        is_personal=True,
        cache_time=0,
    )


if __name__ == '__main__':
    load_dotenv()

    if sentry_dsn := os.getenv('SENTRY_DSN'):
        ss.init(
            dsn=sentry_dsn,
            traces_sample_rate=1.0
        )

    session_username = os.getenv('IG_SESSION_USERNAME')
    session_password = os.getenv('IG_SESSION_PASSWORD')

    log.info('creating instagram client...')
    c = ig.Client(logger=log)

    c.login(session_username, session_password, relogin=True)
    log.info('successfully logged in')

    executor = ThreadPoolExecutor(max_workers=1)

    bot_url = os.getenv('BOT_URL')
    bot_token = os.getenv('BOT_TOKEN')
    bot_port = int(os.getenv('BOT_PORT'))
    bot_persistence_path = Path(
        os.getenv('BOT_PERSISTENCE_PATH'),
        'persistence.pickle',
    )

    persistence = PicklePersistence(
        filepath=bot_persistence_path,
        store_data=PersistenceInput(
            bot_data=True,
            chat_data=False,
            user_data=False,
            callback_data=False,
        ),
    )

    app = ApplicationBuilder() \
        .token(bot_token) \
        .persistence(persistence) \
        .build()

    app.add_handler(InlineQueryHandler(inline_query_handler))

    app.run_webhook(
        listen='0.0.0.0',
        port=bot_port,
        url_path=bot_token,
        webhook_url='/'.join([bot_url, bot_token]),
    )
