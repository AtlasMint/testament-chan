# For fun, grain of salt program

import discord
from discord.ext import commands
from discord import app_commands
import json
import datetime
import os
from dotenv import load_dotenv
import google.generativeai as genai
import time # Make sure to import the time module at the top of your file

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()

# Load tokens from the .env file
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Pre-run Checks ---
if not DISCORD_TOKEN:
    print("Error: DISCORD_TOKEN not found in .env file.")
    exit()
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit()

# --- Gemini API Setup ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash-001')
    print("Gemini API configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    exit()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# This will store user IDs and the timestamp of their last command
gemini_cooldowns = {}
COOLDOWN_SECONDS = 5

@bot.event
async def on_ready():
    """Runs when the bot is connected and ready."""
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f'{bot.user} is now online and ready!')

@bot.event
async def on_message(message):
    # Prevent the bot from replying to itself
    if message.author == bot.user:
        return

    message_content = message.content.lower()

    # --- We want to apply a cooldown to these specific responses ---
    trigger_phrases = [
        'ruby-chan', 'ruby chan', 'nani ga suki?', 'wachi ate fries'
    ]

    if message_content in trigger_phrases:
        # --- COOLDOWN LOGIC MOVED INSIDE ---
        user_id = message.author.id
        current_time = time.time()

        if user_id in gemini_cooldowns:
            last_call_time = gemini_cooldowns[user_id]
            # If the user is on cooldown, silently ignore this message.
            if current_time - last_call_time < COOLDOWN_SECONDS:
                print(f"User {message.author.display_name} is on cooldown for simple replies.")
                return 
        
        # If we've gotten this far, the user is not on cooldown.
        # Now we can send the response AND THEN update their timestamp.
        if message_content == 'ruby-chan' or message_content == 'ruby chan':
            await message.channel.send('hai~!')
        elif message_content == 'nani ga suki?':
            await message.channel.send('chocoominto yori mo a-na-ta <3')
        elif message_content == 'wachi ate fries':
        # Define the path to your image
        # This assumes your script is in the root folder and the image is in /images/
            image_path = 'assets/images/Wachi_ate_fries.jpeg'
            
            try:
                # Create a discord.File object and send it
                await message.channel.send(file=discord.File(image_path))
            except FileNotFoundError:
                print("Error: The image file was not found at the specified path.")
                await message.channel.send("Oops! Wachi too short, not found")

        # Update the user's cooldown timestamp AFTER responding.
        gemini_cooldowns[user_id] = current_time
    
    # Allow other bot commands to be processed
    await bot.process_commands(message)

# --- Helper Function to Split Long Messages ---
def split_message(content, max_length=1980):
    """Splits a string into chunks that are safe for Discord's character limit."""
    if len(content) <= max_length:
        return [content]
    
    parts = []
    while len(content) > 0:
        if len(content) > max_length:
            split_point = content.rfind('\n', 0, max_length)
            if split_point == -1:
                split_point = max_length
            parts.append(content[:split_point])
            content = content[split_point:].lstrip()
        else:
            parts.append(content)
            break
    return parts

# --- /summarize Command ---
@bot.tree.command(name="summarize", description="Uses Gemini to analyze chat history and answer a prompt.")
@app_commands.describe(
    prompt="Your question or prompt for the AI to answer based on the chat history.",
    start_date="Optional: The start date (YYYY-MM-DD) for the history.",
    end_date="Optional: The end date (YYYY-MM-DD) for the history."
)
async def summarize(interaction: discord.Interaction, prompt: str, start_date: str = None, end_date: str = None):
    """Analyzes chat history with Gemini."""
    await interaction.response.defer(thinking=True, ephemeral=True)

    after_date, before_date = None, None
    try:
        if start_date: after_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        if end_date: before_date = datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        await interaction.followup.send("❌ **Invalid Date Format!** Please use `YYYY-MM-DD`.", ephemeral=True)
        return

    try:
        channel = interaction.channel
        print(f"Fetching history for Gemini analysis in #{channel.name}...")
        
        message_contents = []
        async for message in channel.history(limit=5000, after=after_date, before=before_date):
            if message.author.bot or not message.content:
                continue # Skip bots and empty messages
            message_contents.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author.display_name}: {message.content}")
        
        if not message_contents:
            await interaction.followup.send("ℹ️ No messages found in the specified date range to analyze.", ephemeral=True)
            return

        message_contents.reverse()
        full_chat_log = "\n".join(message_contents)

        # Construct the final prompt for the Gemini model
        final_prompt = (
            "You are an AI assistant tasked with analyzing a Discord chat history to answer a user's question.\n"
            "Analyze the following chat log and provide a concise, clear answer to the user's prompt.\n\n"
            f"--- USER'S PROMPT ---\n{prompt}\n\n"
            f"--- CHAT HISTORY ---\n{full_chat_log}\n\n"
            "--- YOUR ANALYSIS ---\n"
        )
        
        print("Sending request to Gemini API...")
        response = gemini_model.generate_content(final_prompt) #FIXME
        
        await interaction.followup.send(f"**Your Prompt:**\n> {prompt}\n\n**Gemini's Analysis:**", ephemeral=True)
        
        # Send the response, splitting it if it's too long
        for part in split_message(response.text):
            await interaction.followup.send(part, ephemeral=True)

    except Exception as e:
        print(f"An unexpected error occurred during summarization: {e}")
        await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

# --- /export Command (from previous version) ---
@bot.tree.command(name="export", description="Exports the chat history of this channel to a JSON file.")
@app_commands.describe(
    start_date="Optional: The start date (YYYY-MM-DD) for the export.",
    end_date="Optional: The end date (YYYY-MM-DD) for the export."
)
async def export(interaction: discord.Interaction, start_date: str = None, end_date: str = None):
    """Exports chat history to a file."""
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    after_date, before_date = None, None
    try:
        if start_date: after_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        if end_date: before_date = datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        await interaction.followup.send("❌ **Invalid Date Format!** Please use `YYYY-MM-DD`.", ephemeral=True)
        return

    try:
        channel = interaction.channel
        messages_data = []
        async for message in channel.history(limit=None, after=after_date, before=before_date):
            messages_data.append({'id': message.id, 'author': str(message.author), 'timestamp_utc': message.created_at.isoformat(), 'content': message.content, 'attachments': [att.url for att in message.attachments]})
        
        if not messages_data:
            await interaction.followup.send("ℹ️ No messages found in the specified date range.", ephemeral=True)
            return

        messages_data.reverse()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{channel.name}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(messages_data, f, ensure_ascii=False, indent=4)
        
        await interaction.followup.send("✅ **Export Complete!** Here is your file.", file=discord.File(filename), ephemeral=True)
        os.remove(filename)
    except Exception as e:
        print(f"An unexpected error occurred during export: {e}")
        await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

# --- Run the Bot ---
bot.run(DISCORD_TOKEN)
