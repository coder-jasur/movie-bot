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

    def format_caption(self, data, country_str=None, lang_str=None, genres_str=None, code=None, quality=None):
        # We try to use data from TMDB but fallback to provided strings
        title = data.get('title', 'N/A')
        year = data.get('release_date', 'N/A')[:4]
        imdb = data.get('vote_average', '0.0')
        
        # Format countries with flags if possible (simple fallback)
        countries = country_str or ", ".join([c["name"] for c in data.get("production_countries", [])])
        
        # Format languages with flags if possible
        langs = lang_str or ", ".join([l["english_name"] for l in data.get("spoken_languages", [])])
        
        # Format genres as hashtags
        if genres_str:
            # If genres_str is provided, we assume it's a comma separated or space separated string
            # We convert it to hashtags
            genres_list = genres_str.replace(",", " ").split()
            genres = " ".join([f"#{g.strip()}" for g in genres_list if g.strip()])
        else:
            genres = " ".join([f"#{g['name']}" for g in data.get("genres", [])])
        
        caption = f"""
🎬 <b>NOMI:</b> {title.upper()} ({year})

💾 <b>KINO KODI:</b> <code>{code or '????'}</code>
📼 <b>SIFATI:</b> {quality or 'HD'}
⭐ <b>IMDb:</b> {imdb}/10
🌍 <b>DAVLATI:</b> {countries}
🌐 <b>TILI:</b> {langs}
🎭 <b>JANRI:</b> {genres}

🚀 <b>KINO KO'RISH UCHUN:</b> @MovieNetBot
👉 <b>KODNI YUBORING:</b> <code>{code or '????'}</code>
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
