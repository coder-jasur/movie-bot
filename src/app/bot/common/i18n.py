from aiogram.utils.i18n import I18n

i18n = I18n(path="translations", default_locale="uz", domain="messages")
gettext = i18n.gettext
lazy_gettext = i18n.lazy_gettext
