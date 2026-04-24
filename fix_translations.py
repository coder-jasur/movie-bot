import os

en_path = 'translations/en/LC_MESSAGES/messages.po'
uz_path = 'translations/uz/LC_MESSAGES/messages.po'

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

def append_to_po(path, content):
    with open(path, 'r', encoding='utf-8') as f:
        existing = f.read()
    
    parts = content.strip().split('\n\n')
    to_add = []
    for p in parts:
        msgid_line = p.split('\n')[0]
        if msgid_line not in existing:
            to_add.append(p)
    
    if to_add:
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\n' + '\n\n'.join(to_add) + '\n')
        print(f"Updated {path}")

if os.path.exists(en_path):
    append_to_po(en_path, en_content)
if os.path.exists(uz_path):
    append_to_po(uz_path, uz_content)
