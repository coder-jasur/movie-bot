import os

files = [
    'translations/ru/LC_MESSAGES/messages.po',
    'translations/en/LC_MESSAGES/messages.po',
    'translations/uz/LC_MESSAGES/messages.po'
]

ru_content = """
msgid "📢 <b>Auto Posting Kanallari</b>\\n\\nJami: {count} ta"
msgstr "📢 <b>Каналы автопостинга</b>\\n\\nВсего: {count} шт"

msgid "🆔 Kanal ID raqamini yuboring yoki kanaldan xabarni forward qiling:"
msgstr "🆔 Отправьте ID канала или перешлите сообщение из канала:"

msgid "📊 <b>Kanal ma'lumotlari:</b>\\n\\n nomi: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nHolati: {channel.channel_status}"
msgstr "📊 <b>Данные канала:</b>\\n\\n название: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nСтатус: {channel.channel_status}"

msgid "⬅️ Bekor qilish"
msgstr "⬅️ Отмена"

msgid "❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring."
msgstr "❌ Пожалуйста, отправьте ID канала или перешлите сообщение из него."
"""

en_content = """
msgid "📢 <b>Auto Posting Kanallari</b>\\n\\nJami: {count} ta"
msgstr "📢 <b>Auto Posting Channels</b>\\n\\nTotal: {count}"

msgid "🆔 Kanal ID raqamini yuboring yoki kanaldan xabarni forward qiling:"
msgstr "🆔 Send channel ID or forward a message from the channel:"

msgid "📊 <b>Kanal ma'lumotlari:</b>\\n\\n nomi: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nHolati: {channel.channel_status}"
msgstr "📊 <b>Channel Data:</b>\\n\\n name: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nStatus: {channel.channel_status}"

msgid "⬅️ Bekor qilish"
msgstr "⬅️ Cancel"

msgid "❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring."
msgstr "❌ Please send the channel ID or forward a message from it."
"""

uz_content = """
msgid "📢 <b>Auto Posting Kanallari</b>\\n\\nJami: {count} ta"
msgstr "📢 <b>Auto Posting Kanallari</b>\\n\\nJami: {count} ta"

msgid "🆔 Kanal ID raqamini yuboring yoki kanaldan xabarni forward qiling:"
msgstr "🆔 Kanal ID raqamini yuboring yoki kanaldan xabarni forward qiling:"

msgid "📊 <b>Kanal ma'lumotlari:</b>\\n\\n nomi: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nHolati: {channel.channel_status}"
msgstr "📊 <b>Kanal ma'lumotlari:</b>\\n\\n nomi: {channel.channel_name}\\nID: <code>{channel.channel_id}</code>\\nUsername: @{channel.channel_username}\\nHolati: {channel.channel_status}"

msgid "⬅️ Bekor qilish"
msgstr "⬅️ Bekor qilish"

msgid "❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring."
msgstr "❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring."
"""

def append_if_not_exists(filepath, content):
    with open(filepath, 'r', encoding='utf-8') as f:
        existing = f.read()
    
    # Check for individual msgids to avoid double appending
    new_parts = []
    for partial in content.strip().split('\n\n'):
        msgid_line = partial.split('\n')[0]
        if msgid_line not in existing:
            new_parts.append(partial)
    
    if new_parts:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write('\n' + '\n\n'.join(new_parts) + '\n')
        print(f"Updated {filepath}")
    else:
        print(f"No new translations for {filepath}")

append_if_not_exists(files[0], ru_content)
append_if_not_exists(files[1], en_content)
append_if_not_exists(files[2], uz_content)
