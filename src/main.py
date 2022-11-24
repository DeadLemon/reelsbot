import logging
import os
import uuid
from asyncio import wrap_future
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    List,
    Optional,
    Tuple,
)
from urllib import parse

from dotenv import load_dotenv
from instaloader import (
    BadResponseException,
    Instaloader,
    Post,
)
from telegram import (
    InlineQueryResultCachedVideo,
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

from src.login import make_login_conversation_handler

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if query == '':
        return

    log.info(
        'inline query received, user_id=%s, username=%s, query=%s',
        update.effective_user.id,
        update.effective_user.username,
        update.inline_query.query,
    )

    shortcode = get_reel_shortcode_from_string(query)
    if not shortcode:
        log.info('failed to get reel shortcode from query: %s', update.inline_query.query)
        return

    if video_file_id := context.bot_data.get(shortcode):
        log.info('returning video from in-memory cache: %s', video_file_id)
        await update.inline_query.answer(
            [
                InlineQueryResultCachedVideo(
                    id=str(uuid.uuid4()),
                    video_file_id=video_file_id,
                    title=shortcode,
                ),
            ],
            is_personal=True,
            cache_time=0,
        )
        return

    video, thumb = await download_reel(executor, loader, shortcode)
    if not video:
        return

    await update.inline_query.answer(
        [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url='/'.join([bot_url, video.as_posix()]),
                mime_type='video/mp4',
                thumb_url='/'.join([bot_url, thumb.as_posix()]) if thumb else None,
                title=shortcode,
            )
        ],
        is_personal=True,
        cache_time=0,
    )


def get_reel_shortcode_from_string(raw: str) -> Optional[str]:
    try:
        split = parse.urlsplit(raw)
    except Exception as e:
        print(e)
        return None

    if split.netloc not in ('www.instagram.com', 'instagram.com'):
        return None

    if not split.path.startswith('/reel/'):
        return None

    return split.path.lstrip('/reel/').rstrip('/')


async def download_reel(executor: ThreadPoolExecutor, loader_: Instaloader, shortcode: str):
    path = Path(downloads_path, 'reels', shortcode)

    def inner() -> Tuple[Optional[Path], Optional[Path]]:
        post = Post.from_shortcode(loader_.context, shortcode)
        try:
            loader_.download_post(post, path)
        except BadResponseException:
            return None, None

        files: List[str] = os.listdir(path)

        video: Optional[Path] = next((Path(path, file) for file in files if file.endswith('.mp4')), None)
        thumb: Optional[Path] = next((Path(path, file) for file in files if file.endswith('.jpg')), None)

        if not video:
            return None, None

        return video, thumb

    return await wrap_future(executor.submit(inner))


if __name__ == '__main__':
    load_dotenv()

    session_username = os.getenv('IG_SESSION_USERNAME')
    session_filename = os.getenv('IG_SESSION_FILENAME')
    downloads_path = os.getenv('IG_DOWNLOADS_PATH')

    loader = Instaloader()
    loader.load_session_from_file(session_username, filename=session_filename)

    executor = ThreadPoolExecutor()

    bot_url = os.getenv('BOT_URL')
    bot_token = os.getenv('BOT_TOKEN')
    bot_port = int(os.getenv('BOT_PORT'))
    bot_persistence_path = os.getenv('BOT_PERSISTENCE_PATH')
    bot_admin_user_id = int(os.getenv('BOT_ADMIN_USER_ID'))

    persistence = PicklePersistence(
        filepath=Path(
            bot_persistence_path,
            'persistence.pickle',
        ),
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

    app.add_handler(make_login_conversation_handler())
    app.add_handler(InlineQueryHandler(inline_query_handler))

    app.run_webhook(
        listen='0.0.0.0',
        port=bot_port,
        url_path=bot_token,
        webhook_url='/'.join([bot_url, bot_token]),
    )
