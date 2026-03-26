from pathlib import Path

from aiogram.utils.i18n import I18n

_I18N_PATH = Path(__file__).resolve().parents[4] / "translations"
i18n = I18n(path=_I18N_PATH, default_locale="uz", domain="messages")
gettext = i18n.gettext
lazy_gettext = i18n.lazy_gettext
