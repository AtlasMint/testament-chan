import discord
import json
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = 1142054150373384262 

start_date = datetime.datetime(2025, 5, 1)
end_date = None

if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found in .env file.")
    exit()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print('Fetching messages...')

    try:
        channel = client.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Error: Channel with ID {CHANNEL_ID} not found.")
            await client.close()
            return
            
        messages_data = []
        async for message in channel.history(limit=None, after=start_date, before=end_date):
            messages_data.append({
                'id': message.id,
                'author': str(message.author),
                'timestamp_utc': message.created_at.isoformat(),
                'content': message.content,
                'attachments': [att.url for att in message.attachments]
            })
        
        messages_data.reverse()
        date_str = f"_{start_date.strftime('%Y-%m-%d') if start_date else 'start'}"
        date_str += f"_{end_date.strftime('%Y-%m-%d') if end_date else 'end'}"
        filename = f"{channel.name}_export{date_str}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(messages_data, f, ensure_ascii=False, indent=4)
            
        print(f"Success! Exported {len(messages_data)} messages to '{filename}'.")

    except discord.errors.Forbidden:
        print("Error: Missing permissions (View Channel, Read Message History).")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        await client.close()

try:
    client.run(TOKEN)
except discord.errors.LoginFailure:
    print("Error: Invalid bot token.")
except Exception as e:
    print(f"Error while running the bot: {e}")
