from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client

if __name__ == '__main__':
    load_dotenv()
    session_username = getenv('IG_USERNAME')
    session_password = getenv('IG_PASSWORD')
    session_settings_path = Path(getenv('IG_SETTINGS_PATH'))
    c = Client()
    c.load_settings(session_settings_path)
    c.login(session_username, session_password)
    c.dump_settings(session_settings_path)
