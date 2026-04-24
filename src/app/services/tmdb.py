import aiohttp
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

class TMDBService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    async def search_movie(self, name: str):
        url = f"{self.base_url}/search/movie?api_key={self.api_key}&query={quote(name)}&language=en-US"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    r = await response.json()
                    if not r.get("results"):
                        return None
                    return r["results"][0]
        except Exception as e:
            logger.error(f"TMDB search error: {e}")
            return None

    async def get_details(self, movie_id: int):
        url = f"{self.base_url}/movie/{movie_id}?api_key={self.api_key}&append_to_response=images"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"TMDB details error: {e}")
            return {}

    def get_best_preview(self, data):
        images = data.get("images", {})
        backdrops = images.get("backdrops", [])
        if backdrops:
            best = max(backdrops, key=lambda x: x["width"])
            return f"https://image.tmdb.org/t/p/original{best['file_path']}"
        posters = images.get("posters", [])
        if posters:
            best = max(posters, key=lambda x: x["width"])
            # Using original or largest poster if no backdrops
            return f"https://image.tmdb.org/t/p/original{best['file_path']}"
        return None

    def format_caption(self, data, country_str=None, lang_str=None, genres_str=None, code=None, quality=None, all_langs=None, target_lang='uz'):
        # Labels mapping
        labels = {
            'uz': {
                'name': '🎬 <b>NOMI:</b>',
                'year': '📆 <b>YILI:</b>',
                'quality': '📼 <b>SIFATI:</b>',
                'imdb': '🌟 <b>IMDb:</b>',
                'country': '🌍 <b>DAVLATI:</b>',
                'lang': '🌐 <b>TILI:</b>',
                'genre': '🎭 <b>JANRI:</b>',
                'code_label': '💾 <b>KINO KODI:</b>',
                'watch': '🚀 <b>KINO KO\'RISH UCHUN:</b>',
                'send_code': '👉 <b>KODNI YUBORING:</b>',
                'attention': '🚨 <b>DIQQAT! Kinoni ko\'rish uchun @MovieNetBot ga kiring va «<code>{code}</code>» kodini yuboring!</b>'
            },
            'ru': {
                'name': '🎬 <b>НАЗВАНИЕ:</b>',
                'year': '📆 <b>ГОД:</b>',
                'quality': '📼 <b>КАЧЕСТВО:</b>',
                'imdb': '🌟 <b>IMDb:</b>',
                'country': '🌍 <b>СТРАНА:</b>',
                'lang': '🌐 <b>ЯЗЫК:</b>',
                'genre': '🎭 <b>ЖАНР:</b>',
                'code_label': '💾 <b>КОД КИНО:</b>',
                'watch': '🚀 <b>СМОТРЕТЬ КИНО:</b>',
                'send_code': '👉 <b>ОТПРАВЬТЕ КОД:</b>',
                'attention': '🚨 <b>ВНИМАНИЕ! Чтобы посмотреть фильм, зайдите в @MovieNetBot и отправьте код «<code>{code}</code>»!</b>'
            },
            'en': {
                'name': '🎬 <b>NAME:</b>',
                'year': '📆 <b>YEAR:</b>',
                'quality': '📼 <b>QUALITY:</b>',
                'imdb': '🌟 <b>IMDb:</b>',
                'country': '🌍 <b>COUNTRY:</b>',
                'lang': '🌐 <b>LANGUAGE:</b>',
                'genre': '🎭 <b>GENRE:</b>',
                'code_label': '💾 <b>MOVIE CODE:</b>',
                'watch': '🚀 <b>TO WATCH MOVIE:</b>',
                'send_code': '👉 <b>SEND CODE:</b>',
                'attention': '🚨 <b>ATTENTION! To watch the movie, go to @MovieNetBot and send the code «<code>{code}</code>»!</b>'
            }
        }

        lang = target_lang if target_lang in labels else 'uz'
        L = labels[lang]

        # Prefer passed title override if present
        title = data.get('title') or 'N/A'
        # Round IMDb score to 1 decimal place
        imdb_val = data.get('vote_average', 0.0)
        imdb = f"{float(imdb_val):.1f}"
        
        # Release year
        year = data.get('release_date', 'N/A')[:4]
        
        # Country mapping for Uz and Ru
        country_maps = {
            'uz': {
                'USA': 'AQSH 🇺🇸', 'United States of America': 'AQSH 🇺🇸',
                'UK': 'Buyuk Britaniya 🇬🇧', 'United Kingdom': 'Buyuk Britaniya 🇬🇧',
                'Russia': 'Rossiya 🇷🇺', 'Russian Federation': 'Rossiya 🇷🇺',
                'Turkey': 'Turkiya 🇹🇷', 'France': 'Fransiya 🇫🇷', 'Germany': 'Germaniya 🇩🇪',
                'India': 'Hindiston 🇮🇳', 'China': 'Xitoy 🇨🇳', 'Japan': 'Yaponiya 🇯🇵',
                'South Korea': 'Janubiy Koreya 🇰🇷', 'Italy': 'Italiya 🇮🇹',
                'Spain': 'Ispaniya 🇪🇸', 'Canada': 'Kanada 🇨🇦', 'Australia': 'Avstraliya 🇦🇺',
                'Brazil': 'Braziliya 🇧🇷', 'Mexico': 'Meksika 🇲🇽', 'Uzbekistan': 'O\'zbekiston 🇺🇿'
            },
            'ru': {
                'USA': 'США 🇺🇸', 'United States of America': 'США 🇺🇸',
                'UK': 'Великобритания 🇬🇧', 'United Kingdom': 'Великобритания 🇬🇧',
                'Russia': 'Россия 🇷🇺', 'Russian Federation': 'Россия 🇷🇺',
                'Turkey': 'Турция 🇹🇷', 'France': 'Франция 🇫🇷', 'Germany': 'Германия 🇩🇪',
                'India': 'Индия 🇮🇳', 'China': 'Китай 🇨🇳', 'Japan': 'Япония 🇯🇵',
                'South Korea': 'Южная Корея 🇰🇷', 'Italy': 'Италия 🇮🇹',
                'Spain': 'Испания 🇪🇸', 'Canada': 'Канада 🇨🇦', 'Australia': 'Австралия 🇦🇺',
                'Brazil': 'Бразилия 🇧🇷', 'Mexico': 'Мексика 🇲🇽', 'Uzbekistan': 'Узбекистан 🇺🇿'
            }
        }
        
        c_map = country_maps.get(lang, {})
        
        raw_countries = [c["name"] for c in data.get("production_countries", [])]
        translated_countries = [c_map.get(c, c) for c in raw_countries]
        countries = country_str or ", ".join(translated_countries)
        
        # Languages handling
        if all_langs:
            # Format: Uzbekcha 🇺🇿, Ruscha 🇷🇺
            lang_displays = []
            for l_code in all_langs:
                if l_code == 'uz': lang_displays.append("O'zbekcha 🇺🇿")
                elif l_code == 'ru': lang_displays.append("Ruscha 🇷🇺")
                elif l_code == 'en': lang_displays.append("Inglizcha 🇺🇸")
                else: lang_displays.append(f"{l_code.upper()}")
            langs = ", ".join(lang_displays)
        else:
            langs = lang_str or "N/A"

        # Genres processing
        if genres_str:
            genres_list = genres_str.replace(",", " ").split()
            genres = " ".join([f"#{g.strip()}" for g in genres_list if g.strip()])
        else:
            genres = " ".join([f"#{g['name']}" for g in data.get("genres", [])])
        
        caption = f"""
{L['name']} <b>{title.upper()} ({year})</b>

{L['code_label']} <code>{code or '????'}</code>
{L['quality']} <b>{quality or '720p'}</b>
{L['imdb']} <b>{imdb}/10</b>
{L['country']} <b>{countries}</b>
{L['lang']} <b>{langs}</b>
{L['genre']} <b>{genres}</b>

{L['watch']} @MovieNetBot
{L['send_code']} <code>{code or '????'}</code>

{L['attention'].format(code=code or '????')}
""".strip()
        return caption

    async def parse_movie(self, movie_name: str):
        movie = await self.search_movie(movie_name)
        if not movie:
            return None
        data = await self.get_details(movie["id"])
        preview = self.get_best_preview(data)
        return {
            "data": data,
            "preview": preview,
            "tmdb_id": movie["id"]
        }
