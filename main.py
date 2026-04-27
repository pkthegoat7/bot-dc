import discord
from discord.ext import tasks, commands
import os
import random
import yt_dlp
import asyncio
from supabase import create_client
# Importações para o Keep Alive (Essencial para o Render)
import http.server
import socketserver
import threading

# --- CONFIGURAÇÕES ---
TOKEN = os.getenv('DISCORD_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
BUCKET_NAME = "bot-icons"

INTERVALO_ICONES = 3600  # Envia um ícone a cada 1 hora
NOME_CANAL_ALVO = "icons-aleatorios"

# --- SISTEMA KEEP ALIVE ---
def keep_alive():
    """Cria um servidor web simples para o Render não dar timeout no bot."""
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"📡 Keep Alive: Servidor rodando na porta {port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Erro no Keep Alive: {e}")

# --- CONEXÃO SUPABASE ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        # Inicia o loop automático de ícones
        self.enviar_icones_loop.start()

    async def on_ready(self):
        print(f'✅ Bot online como {self.user.name}')

    # --- LOOP DE ÍCONES ---
    @tasks.loop(seconds=INTERVALO_ICONES)
    async def enviar_icones_loop(self):
        try:
            # Lista arquivos no bucket do Supabase
            res = supabase.storage.from_(BUCKET_NAME).list(options={'limit': 5000})
            if not res:
                return

            # Escolhe uma foto aleatória
            foto_info = random.choice(res)
            foto_nome = foto_info['name']
            url_publica = supabase.storage.from_(BUCKET_NAME).get_public_url(foto_nome)

            # Envia para o canal 'icons-aleatorios' em todos os servidores
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

    # --- COMANDOS ---
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

            ctx.voice_client.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options))
            await ctx.send(f'🎶 Tocando agora: **{data["title"]}**')

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Parou!")

# --- START ---
if __name__ == "__main__":
    # Roda o servidor Keep Alive em uma thread separada
    threading.Thread(target=keep_alive, daemon=True).start()
    
    bot = MyBot()
    bot.run(TOKEN)