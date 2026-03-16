from src.app.bot.common.i18n import lazy_gettext as _

# --- Main Menu ---
BTN_MOVIES = _("🎬 Kino")
BTN_ANIME = _("🎌 Anime")
BTN_CARTOON = _("🎨 Multfilm")
BTN_FAVORITES = _("⭐ Sevimlilar")
BTN_VIP = _("💎 VIP tarif")
BTN_PROFILE = _("👤 Shaxsiy kabinet")

# --- Common ---
BTN_BACK = _("⬅️ Orqaga")

# --- Cinema Sub-menu ---
BTN_RND_FILM = _("🎥 Tasodifiy film")
BTN_RND_SERIES = _("📺 Tasodifiy serial")
BTN_RND_MINI = _("🎞️ Tasodifiy epizodli film")
BTN_TOP_MOVIES = _("🔝 Top filmlar")
BTN_GENRE_MOVIES = _("🎭 Janr bo'yicha filmlar")

# --- Anime Sub-menu ---
BTN_RND_ANIME = _("🎥 Tasodifiy anime")
BTN_RND_ANIME_SERIES = _("📺 Tasodifiy anime serial")
BTN_RND_ANIME_MINI = _("🎞️ Tasodifiy epizodli anime")
BTN_TOP_ANIME = _("🔝 Top animelar")
BTN_GENRE_ANIME = _("🎭 Janr bo'yicha anime")

# --- Cartoon Sub-menu ---
BTN_RND_CARTOON = _("🎥 Tasodifiy Multfilm")
BTN_RND_CARTOON_SERIES = _("📺 Tasodifiy Mult-Serial")
BTN_RND_CARTOON_MINI = _("🎞️ Tasodifiy Epizodli Multfilm")
BTN_TOP_CARTOON = _("🔝 Top Multfilmlar")
BTN_GENRE_CARTOON = _("🎭 Janr bo'yicha multfilm")

# --- Lists for Filters ---
# Using list for filters to support both new and legacy if needed, 
# but for now we focus on new. Legacy support might need raw strings.

LIST_TOP_MOVIES = [BTN_TOP_MOVIES]
LIST_TOP_ANIME = [BTN_TOP_ANIME]
LIST_TOP_CARTOON = [BTN_TOP_CARTOON]

LIST_GENRE_MOVIES = [BTN_GENRE_MOVIES]
LIST_GENRE_ANIME = [BTN_GENRE_ANIME]
LIST_GENRE_CARTOON = [BTN_GENRE_CARTOON]
