import logging
from urllib.parse import quote

import aiohttp

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

    async def get_localized_title(self, movie_id: int, language: str):
        url = f"{self.base_url}/movie/{movie_id}?api_key={self.api_key}&language={language}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    r = await response.json()
                    return r.get("title")
        except Exception as e:
            logger.error(f"TMDB localized title error: {e}")
            return None

    def get_best_preview(self, data):
        images = data.get("images", {})
        # Prefer backdrops (horizontal) as requested now
        backdrops = images.get("backdrops", [])
        if backdrops:
            best = max(backdrops, key=lambda x: x["width"])
            return f"https://image.tmdb.org/t/p/original{best['file_path']}"

        posters = images.get("posters", [])
        if posters:
            # Sort by width to get highest quality
            best = max(posters, key=lambda x: x["width"])
            return f"https://image.tmdb.org/t/p/original{best['file_path']}"
        return None

    def get_all_backdrops(self, data):
        images = data.get("images", {})
        backdrops = images.get("backdrops", [])
        return [
            f"https://image.tmdb.org/t/p/original{p['file_path']}" for p in backdrops
        ]

    def get_all_posters(self, data):
        images = data.get("images", {})
        posters = images.get("posters", [])
        return [f"https://image.tmdb.org/t/p/original{p['file_path']}" for p in posters]

    def _html_to_entities(self, html_text: str):
        import re

        from aiogram.types import MessageEntity

        plain = ""
        entities = []
        stack = []

        tag_pattern = re.compile(
            r"<(/?)(tg-emoji|b|i|u|s|code|pre|a)([^>]*)>|" r"&amp;|&lt;|&gt;|&quot;"
        )

        pos = 0
        for m in tag_pattern.finditer(html_text):
            plain += html_text[pos : m.start()]
            pos = m.end()

            token = m.group(0)

            if token == "&amp;":
                plain += "&"
                continue
            if token == "&lt;":
                plain += "<"
                continue
            if token == "&gt;":
                plain += ">"
                continue
            if token == "&quot;":
                plain += '"'
                continue

            closing = m.group(1) == "/"
            tag = m.group(2)
            attrs = m.group(3)

            if not closing:
                start = len(plain.encode("utf-16-le")) // 2
                if tag == "tg-emoji":
                    eid_m = re.search(r'emoji-id="(\d+)"', attrs)
                    eid = eid_m.group(1) if eid_m else None
                    stack.append(("custom_emoji", start, eid))
                elif tag == "b":
                    stack.append(("bold", start, None))
                elif tag == "i":
                    stack.append(("italic", start, None))
                elif tag == "u":
                    stack.append(("underline", start, None))
                elif tag == "s":
                    stack.append(("strikethrough", start, None))
                elif tag == "code":
                    stack.append(("code", start, None))
                elif tag == "pre":
                    stack.append(("pre", start, None))
                elif tag == "a":
                    href_m = re.search(r'href="([^"]*)"', attrs)
                    href = href_m.group(1) if href_m else None
                    stack.append(("text_link", start, href))
            else:
                tag_to_etype = {
                    "tg-emoji": "custom_emoji",
                    "b": "bold",
                    "i": "italic",
                    "u": "underline",
                    "s": "strikethrough",
                    "code": "code",
                    "pre": "pre",
                    "a": "text_link",
                }
                target_etype = tag_to_etype.get(tag)
                for j in range(len(stack) - 1, -1, -1):
                    etype, start, extra = stack[j]
                    if etype == target_etype:
                        stack.pop(j)
                        end = len(plain.encode("utf-16-le")) // 2
                        length = end - start
                        if length > 0:
                            kwargs = {"type": etype, "offset": start, "length": length}
                            if etype == "custom_emoji" and extra:
                                kwargs["custom_emoji_id"] = extra
                            elif etype == "text_link" and extra:
                                kwargs["url"] = extra
                            entities.append(MessageEntity(**kwargs))
                        break

        plain += html_text[pos:]
        return plain, entities

    def format_caption(
        self,
        data,
        country_str=None,
        lang_str=None,
        genres_str=None,
        code=None,
        quality=None,
        all_langs=None,
        target_lang="uz",
    ):
        # Custom Emojis Mapping
        E = {
            "name": '<tg-emoji emoji-id="5375464961822695044">🎬</tg-emoji>',
            "year": '<tg-emoji emoji-id="5431897022456145283">📆</tg-emoji>',
            "quality": '<tg-emoji emoji-id="5375309569905938163">📹</tg-emoji>',
            "imdb": '<tg-emoji emoji-id="5346242859039209592">🌟</tg-emoji>',
            "country": '<tg-emoji emoji-id="5314361729117855941">🌍</tg-emoji>',
            "lang": '<tg-emoji emoji-id="5447410659077661506">🌐</tg-emoji>',
            "genre": '<tg-emoji emoji-id="5359441070201513074">🎭</tg-emoji>',
            "code": '<tg-emoji emoji-id="5472238215748397135">🔢</tg-emoji>',
            "watch": '<tg-emoji emoji-id="5346242859039209592">📱</tg-emoji>',
            "attention": '<tg-emoji emoji-id="5440660757194744323">‼️</tg-emoji>',
        }

        # Labels mapping with custom emojis
        labels = {
            "uz": {
                "name": f"{E['name']} <b>NOMI:</b>",
                "year": f"{E['year']} <b>YILI:</b>",
                "quality": f"{E['quality']} <b>SIFATI:</b>",
                "imdb": f"{E['imdb']} <b>IMDb:</b>",
                "country": f"{E['country']} <b>DAVLATI:</b>",
                "lang": f"{E['lang']} <b>TILI:</b>",
                "genre": f"{E['genre']} <b>JANRI:</b>",
                "code_label": f"{E['code']} <b>KINO KODI:</b>",
                "watch": f"{E['imdb']} <b>KINO KO'RISH UCHUN:</b>",
                "send_code": f"👉 <b>KODNI YUBORING:</b>",
                "attention": f"{E['attention']} <b>DIQQAT! Kinoni ko'rish uchun @MovieNetBot ga kiring va «<code>{code}</code>» kodini yuboring!</b>",
            },
            "ru": {
                "name": f"{E['name']} <b>НАЗВАНИЕ:</b>",
                "year": f"{E['year']} <b>ГОД:</b>",
                "quality": f"{E['quality']} <b>КАЧЕСТВО:</b>",
                "imdb": f"{E['imdb']} <b>IMDb:</b>",
                "country": f"{E['country']} <b>СТРАНА:</b>",
                "lang": f"{E['lang']} <b>ЯЗЫК:</b>",
                "genre": f"{E['genre']} <b>ЖАНР:</b>",
                "code_label": f"{E['code']} <b>КОД КИНО:</b>",
                "watch": f"{E['imdb']} <b>СМОТРЕТЬ КИНО:</b>",
                "send_code": f"👉 <b>ОТПРАВЬТЕ КОД:</b>",
                "attention": f"{E['attention']} <b>ВНИМАНИЕ! Чтобы посмотреть фильм, зайдите в @MovieNetBot и отправьте код «<code>{code}</code>»!</b>",
            },
            "en": {
                "name": f"{E['name']} <b>NAME:</b>",
                "year": f"{E['year']} <b>YEAR:</b>",
                "quality": f"{E['quality']} <b>QUALITY:</b>",
                "imdb": f"{E['imdb']} <b>IMDb:</b>",
                "country": f"{E['country']} <b>COUNTRY:</b>",
                "lang": f"{E['lang']} <b>LANGUAGE:</b>",
                "genre": f"{E['genre']} <b>GENRE:</b>",
                "code_label": f"{E['code']} <b>MOVIE CODE:</b>",
                "watch": f"{E['imdb']} <b>TO WATCH MOVIE:</b>",
                "send_code": f"👉 <b>SEND CODE:</b>",
                "attention": f"{E['attention']} <b>ATTENTION! To watch the movie, go to @MovieNetBot and send the code «<code>{code}</code>»!</b>",
            },
        }

        lang = target_lang if target_lang in labels else "uz"
        L = labels[lang]

        # Prefer passed title override if present
        title = data.get("title") or "N/A"
        # Round IMDb score to 1 decimal place
        imdb_val = data.get("vote_average", 0.0)
        imdb = f"{float(imdb_val):.1f}"

        # Release year
        year = data.get("release_date", "N/A")[:4]

        # Flags mapping
        F = {
            "uz": '<tg-emoji emoji-id="5456133703296097741">🇺🇿</tg-emoji>',
            "ru": '<tg-emoji emoji-id="5449408995691341691">🇷🇺</tg-emoji>',
            "en": '<tg-emoji emoji-id="5202021044105257611">🇺🇸</tg-emoji>',
            "uk": '<tg-emoji emoji-id="5202196682497859879">🇬🇧</tg-emoji>',
            "kz": '<tg-emoji emoji-id="5228885231318088701">🇰🇿</tg-emoji>',
            "ca": '<tg-emoji emoji-id="5404421811720958731">🇨🇦</tg-emoji>',
            "kr": '<tg-emoji emoji-id="5467928327736010821">🇰🇷</tg-emoji>',
            "tr": '<tg-emoji emoji-id="5226948110873278599">🇹🇷</tg-emoji>',
            "cn": '<tg-emoji emoji-id="5431782733376399004">🇨🇳</tg-emoji>',
            "za": '<tg-emoji emoji-id="5323804090164066657">🇿🇦</tg-emoji>',
            "br": '<tg-emoji emoji-id="6118655940829907978">🇧🇷</tg-emoji>',
            "in": '<tg-emoji emoji-id="6136551252781172945">🇮🇳</tg-emoji>',
        }

        # Country mapping for Uz and Ru
        country_maps = {
            "uz": {
                "USA": f'AQSH {F["en"]}',
                "United States of America": f'AQSH {F["en"]}',
                "UK": f'Buyuk Britaniya {F["uk"]}',
                "United Kingdom": f'Buyuk Britaniya {F["uk"]}',
                "Russia": f'Rossiya {F["ru"]}',
                "Russian Federation": f'Rossiya {F["ru"]}',
                "Turkey": f'Turkiya {F["tr"]}',
                "France": f"Fransiya 🇫🇷",
                "Germany": f"Germaniya 🇩🇪",
                "India": f'Hindiston {F["in"]}',
                "China": f'Xitoy {F["cn"]}',
                "Japan": f"Yaponiya 🇯🇵",
                "South Korea": f'Janubiy Koreya {F["kr"]}',
                "Italy": f"Italiya 🇮🇹",
                "Spain": f"Ispaniya 🇪🇸",
                "Canada": f'Kanada {F["ca"]}',
                "Australia": f"Avstraliya 🇦🇺",
                "Brazil": f'Braziliya {F["br"]}',
                "Mexico": f"Meksika 🇲🇽",
                "Uzbekistan": f'O\'zbekiston {F["uz"]}',
            },
            "ru": {
                "USA": f'США {F["en"]}',
                "United States of America": f'США {F["en"]}',
                "UK": f'Великобритания {F["uk"]}',
                "United Kingdom": f'Великобритания {F["uk"]}',
                "Russia": f'Россия {F["ru"]}',
                "Russian Federation": f'Россия {F["ru"]}',
                "Turkey": f'Турция {F["tr"]}',
                "France": f"Франция 🇫🇷",
                "Germany": f"Германия 🇩🇪",
                "India": f'Индия {F["in"]}',
                "China": f'Китай {F["cn"]}',
                "Japan": f"Япония 🇯🇵",
                "Spain": f"Испания 🇪🇸",
                "Canada": f'Канада {F["ca"]}',
                "Australia": f"Австралия 🇦🇺",
                "Brazil": f'Бразилия {F["br"]}',
                "Mexico": f"Мексика 🇲🇽",
                "Uzbekistan": f'Узбекистан {F["uz"]}',
            },
        }

        c_map = country_maps.get(lang, country_maps["uz"])
        raw_countries = [c["name"] for c in data.get("production_countries", [])]
        translated_countries = [c_map.get(c, c) for c in raw_countries]
        countries = country_str or ", ".join(translated_countries)

        # Languages handling
        if all_langs:
            lang_displays = []
            for l_code in all_langs:
                if l_code == "uz":
                    lang_displays.append(f"O'zbekcha {F['uz']}")
                elif l_code == "ru":
                    lang_displays.append(f"Ruscha {F['ru']}")
                elif l_code == "en":
                    lang_displays.append(f"Inglizcha {F['en']}")
                else:
                    lang_displays.append(f"{l_code.upper()}")
            langs = ", ".join(lang_displays)
        else:
            langs = lang_str or "N/A"

        # Genres processing
        if genres_str:
            genres_list = genres_str.replace(",", " ").split()
            genres = " ".join(
                [f"#{g.strip().lstrip('#')}" for g in genres_list if g.strip()]
            )
        else:
            genres = " ".join([f"#{g['name']}" for g in data.get("genres", [])])

        html_caption = f"""
{L['name']} <b>{title.upper()}</b>

{L['year']} <b>{year}</b>
{L['quality']} <b>{quality or '720p'}</b>
{L['imdb']} <b>{imdb}/10</b>
{L['country']} <b>{countries}</b>
{L['lang']} <b>{langs}</b>
{L['genre']} <b>{genres}</b>

{L['code_label']} <code>{code or '????'}</code>

{L['attention'].format(code=code or '????')}
""".strip()

        # Build plain text + MessageEntity list from HTML
        return self._html_to_entities(html_caption)

    async def parse_movie(self, movie_name: str):
        movie = await self.search_movie(movie_name)
        if not movie:
            return None
        data = await self.get_details(movie["id"])
        preview = self.get_best_preview(data)
        return {"data": data, "preview": preview, "tmdb_id": movie["id"]}
