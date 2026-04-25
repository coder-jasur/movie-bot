path = r'src/app/bot/dialog/admin/add_movie.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content_unix = content.replace('\r\n', '\n')

# --- Fix 4th occurrence: on_confirm (indentation 16 spaces) ---
old4 = (
    '                data["post_caption"] = tmdb.format_caption(\n'
    '                    tmdb_result["data"],\n'
    '                    code=data.get("code"),\n'
    '                    genres_str=get_post_hashtags(data.get("genres", [])),\n'
    '                    lang_str=get_language_display_text(data.get("language")),\n'
    '                    quality=data.get("input_quality"),\n'
    '                )\n'
    '            else:\n'
    '                data["post_image"] = data.get("thumbnail_file_id")\n'
    '                data["post_caption"] = (\n'
    '                    f"\U0001f3ac <b>Nomi:</b> {movie_name}\\n\\n\U0001f4be <b>KODI:</b> {data.get(\'code\')}"\n'
    '                )'
)

new4 = (
    '                _cap_text, _cap_entities = tmdb.format_caption(\n'
    '                    tmdb_result["data"],\n'
    '                    code=data.get("code"),\n'
    '                    genres_str=get_post_hashtags(data.get("genres", [])),\n'
    '                    lang_str=get_language_display_text(data.get("language")),\n'
    '                    quality=data.get("input_quality"),\n'
    '                )\n'
    '                data["post_caption"] = _cap_text\n'
    '                data["post_caption_entities"] = [\n'
    '                    e.model_dump() for e in _cap_entities\n'
    '                ]\n'
    '            else:\n'
    '                data["post_image"] = data.get("thumbnail_file_id")\n'
    '                data["post_caption"] = (\n'
    '                    f"\U0001f3ac Nomi: {movie_name}\\n\\n\U0001f4be Kodi: {data.get(\'code\')}"\n'
    '                )\n'
    '                data["post_caption_entities"] = []'
)

count = content_unix.count(old4)
print('Pattern 4 found:', count)

if count > 0:
    updated = content_unix.replace(old4, new4)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(updated.replace('\n', '\r\n'))
    print('Done')
else:
    # Debug: show the actual lines
    idx = content_unix.find('data["post_caption"] = tmdb.format_caption(')
    print('Snippet:')
    print(repr(content_unix[idx-20:idx+400]))
