import pytest

from main import get_reel_shortcode_from_string


@pytest.mark.parametrize(
    'raw,expected', (
            (
                    'https://www.instagram.com/reel/ClOf_Got5wx/?igshid=YmMyMTA2M2Y=',
                    'ClOf_Got5wx'
            ),
            (
                    'https://instagram.com/reel/ClOf_Got5wx/?igshid=YmMyMTA2M2Y=',
                    'ClOf_Got5wx'
            ),
            (
                    'http://instagram.com/reel/ClOf_Got5wx/?igshid=YmMyMTA2M2Y=',
                    'ClOf_Got5wx'
            ),
(
                    'www.instagram.com/reel/ClOf_Got5wx/?igshid=YmMyMTA2M2Y=',
                    'ClOf_Got5wx'
            ),
    )
)
def test_get_reel_shortcode_from_string(raw, expected):
    assert get_reel_shortcode_from_string(raw) == expected
