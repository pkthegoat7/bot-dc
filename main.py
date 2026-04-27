import discord
from discord.ext import tasks, commands
import os
import random
import yt_dlp
import asyncio
from supabase import create_client
import http.server
import socketserver
import threading
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# --- CONFIGURAÇÕES ---
TOKEN = os.getenv('DISCORD_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
BUCKET_NAME = "bot-icons"

INTERVALO_ICONES = 3600  # 1 hora
NOME_CANAL_ALVO = "icons-aleatorios"

# IDs para conexão automática (Substitua pelos IDs Reais do seu Discord)
# Usando int() em strings para evitar erro de zeros à esquerda no Python
ID_SERVIDOR = int("1234567890") 
ID_CANAL_VOZ = int("987654321")

# --- SISTEMA KEEP ALIVE (PARA O RENDER) ---
def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"📡 Keep Alive: Servidor rodando na porta {port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Erro no Keep Alive: {e}")

# --- CONEXÃO SUPABASE ---
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("❌ Erro: SUPABASE_URL ou SUPABASE_KEY não configurados!")

# --- CONFIGURAÇÃO MÚSICA ---
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Inicia os loops automáticos
        self.enviar_icones_loop.start()
        self.connect_to_voice_channel.start()

    async def on_ready(self):
        print(f'✅ Bot online como {self.user.name}')

    # --- LOOP DE CONEXÃO AUTOMÁTICA EM VOZ ---
    @tasks.loop(minutes=2)
    async def connect_to_voice_channel(self):
        try:
            guild = self.get_guild(ID_SERVIDOR)
            if guild:
                channel = guild.get_channel(ID_CANAL_VOZ)
                # Verifica se o bot já não está conectado
                if not discord.utils.get(self.voice_clients, guild=guild):
                    if channel:
                        await channel.connect()
                        print(f"🎙️ Conectado automaticamente ao canal: {channel.name}")
        except Exception as e:
            # CORRIGIDO: Chave fechada corretamente abaixo
            print(f"Erro ao tentar conexão automática de voz: {e}")

    @connect_to_voice_channel.before_loop
    async def before_voice_loop(self):
        await self.wait_until_ready()

    # --- LOOP DE ÍCONES (SUPABASE) ---
    @tasks.loop(seconds=INTERVALO_ICONES)
    async def enviar_icones_loop(self):
        try:
            res = supabase.storage.from_(BUCKET_NAME).list(options={'limit': 5000})
            if not res:
                return

            foto_info = random.choice(res)
            foto_nome = foto_info['name']
            url_publica = supabase.storage.from_(BUCKET_NAME).get_public_url(foto_nome)

            for guild in self.guilds:
                channel = discord.utils.get(guild.text_channels, name=NOME_CANAL_ALVO)
                if channel:
                    embed = discord.Embed(title="✨ Novo Ícone!", color=discord.Color.random())
                    embed.set_image(url=url_publica)
                    await channel.send(embed=embed)
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Erro no loop de ícones: {e}")

    @enviar_icones_loop.before_loop
    async def before_icones_loop(self):
        await self.wait_until_ready()

    # --- COMANDOS DE MÚSICA ---
    @commands.command()
    async def play(self, ctx, *, search):
        if not ctx.author.voice:
            return await ctx.send("Entra num canal de voz primeiro!")
        
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        async with ctx.typing():
            data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ytdl.extract_info(search, download=False)
            )
            if 'entries' in data:
                data = data['entries'][0]

            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()

            ctx.voice_client.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options))
            await ctx.send(f'🎶 Tocando agora: **{data["title"]}**')

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Desconectado!")

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if TOKEN:
        bot = MyBot()
        bot.run(TOKEN)
    else:
        print("❌ Erro: DISCORD_TOKEN não encontrado!")