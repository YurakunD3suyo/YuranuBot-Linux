import discord
from discord import app_commands
from discord import VoiceChannel
import psutil
import platform
import os
import asyncio
import logging
from random import uniform
import sys
import json
import wave
import pydub
import time
import voicevox_core
from voicevox_core import AccelerationMode, AudioQuery, VoicevoxCore
from discord.player import FFmpegOpusAudio
from collections import deque, defaultdict
from dotenv import load_dotenv
import os

ROOT_DIR = os.path.dirname(__file__)
SCRSHOT = os.path.join(ROOT_DIR, "scrshot", "scr.png")

### ロギングを開始
logging.basicConfig(level=logging.DEBUG)

### インテントの生成
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
logging.debug("discord.py -> インテント生成完了")

### クライアントの生成
client = discord.Client(intents=intents, activity=discord.Game(name="CMDTree Testing"))
logging.debug("discord.py -> クライアント生成完了")

### コマンドツリーの作成
tree = app_commands.CommandTree(client=client)
logging.debug("discord.py -> ツリー生成完了")

@client.event
async def on_ready():
    print(f'{client.user}に接続しました！')
    await tree.sync()
    print("コマンドツリーを同期しました")

    rpc_task = asyncio.create_task(performance(client))
    await rpc_task


@tree.command(name="vc-start", description="ユーザーが接続しているボイスチャットに接続するのだ")
async def vc_command(interact: discord.Interaction):
    try:
        if (interact.user.voice is None):
            await interact.response.send_message("ボイスチャンネルに接続していないのだ...")
            return
        if (interact.guild.voice_client is not None):
            await interact.response.send_message("すでにほかのボイスチャンネルにつながっているのだ...")
            return
        
        await interact.user.voice.channel.connect()
        await interact.response.send_message("接続したのだ！")
        await queue_yomiage("接続したのだ。", interact.guild, 1)

    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if (member.bot):##ボットなら無視
        return      
    
    if before.channel != after.channel:
        for bot_client in client.voice_clients:
            ##参加時に読み上げる
            if after.channel is not None:
                if (after.channel.id == bot_client.channel.id):
                    await queue_yomiage(f"{member.name}が参加したのだ。", member.guild, 3)
                    return
                
            ##退席時に読み上げる
            if before.channel is not None:
                if (before.channel.id == bot_client.channel.id):
                    await queue_yomiage(f"{member.name}が退席したのだ。", member.guild, 3)

@client.event ##読み上げ用のイベント
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    
    if (message.guild.voice_client != None):
        await queue_yomiage(message.content, message.guild, 3)

yomiage_serv_list = defaultdict(deque)

## VOICEVOX用の設定
VC_OUTPUT = "./yomiage_data/"
FS = 24000

async def queue_yomiage(content: str, guild: discord.Guild, spkID: int):    
    try:
        core = VoicevoxCore(
            acceleration_mode=AccelerationMode.AUTO,
            open_jtalk_dict_dir = './voicevox/open_jtalk_dic_utf_8-1.11'
        )

        core.load_model(spkID)
        audio_query = core.audio_query(content, spkID)
        wav = core.synthesis(audio_query, spkID)

        ###作成時間を記録するため、timeを利用する
        voice_file = f"{VC_OUTPUT}{guild.id}.wav"

        with wave.open(voice_file, "w") as wf:
            wf.setnchannels(1)  # チャンネル数の設定 (1:mono, 2:stereo)
            wf.setsampwidth(2)
            wf.setframerate(FS) 
            wf.writeframes(wav)  # ステレオデータを書きこむ

        queue = yomiage_serv_list[guild.id]
        queue.append(discord.FFmpegOpusAudio(voice_file))
    
        if not guild.voice_client.is_playing():
            send_voice(queue, guild.voice_client)
        
        return
            
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        task = asyncio.create_task(sendException(e, filename, line_no))

def send_voice(queue, voice_client):
    
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    voice_client.play(source, after=lambda e:send_voice(queue, voice_client))


@tree.command(name="vc-stop", description="ボイスチャンネルから退出するのだ")
async def vc_disconnect_command(interact: discord.Interaction):
    try:
        if ((interact.guild.voice_client is None)):
            await interact.response.send_message("私はボイスチャンネルに接続していないのだ...")
            return
            
        elif((interact.user.voice is None)):
            await interact.response.send_message("ボイスチャンネルに接続していないのだ...入ってから実行するのだ")
            return
        
        await interact.guild.voice_client.disconnect()
        await interact.response.send_message("切断したのだ")
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)

@tree.command(name="test",description=f"なにか")#Thank You shizengakari!!
async def test(interaction: discord.Interaction):

    await interaction.response.send_message(f"test")
    return

@tree.command(name="sbc",description="Shizen Black Companyの説明資料なのだ")#Shizen Black Companyの宣伝
async def sbc_command(interact:discord.Interaction):
    await interact.response.send_message('**Lets Join To "Shizen Black Company" (100% Working)** https://black.shizen.lol')

@tree.command(name="status",description="Botを稼働しているPCの状態を表示するのだ")#PCの状態
async def pc_status(interact: discord.Interaction):
    try:
        os_info = platform.uname()
        os_bit = platform.architecture()[1]

        hard_id = 0
        cpu_Temp = "Not Available"
        cpu_Power = "Not Available"
        cpu_Load = "Not Available"

        yuranu_cpu_load = uniform(67.00, 99.00)
        yuranu_maxmem = float(1.4)
        yuranu_mem_load = uniform(yuranu_maxmem-1, yuranu_maxmem)

        cpu_name = platform.processor()
        cpu_freq = psutil.cpu_freq().current / 1000
        cpu_Load = psutil.cpu_percent(percpu=False)
        cpu_cores = psutil.cpu_count()

        ram_info = psutil.virtual_memory()
        
        py_version = platform.python_version()
        py_buildDate = platform.python_build()[1]

        if (os_info.system == "Windows"): ### Windowsの場合、表記を変更する
            win32_edition = platform.win32_edition()
            win32_ver = os_info.release

            if (win32_edition == "Professional"):
                win32_edition = "Pro"
            
            os_name = f"{os_info.system} {win32_ver} {win32_edition}"

        
        
        embed = discord.Embed( ### Embedを定義する
                        title="よしっ、調査完了っと！これが結果なのだ！",# タイトル
                        color=0x00ff00, # フレーム色指定(今回は緑)
                        description=f"「{client.user}が生息するPCの情報をかき集めてくれたようです。」", # Embedの説明文 必要に応じて
                        )
        
        embed.set_author(name=client.user, # Botのユーザー名
                    icon_url=client.user.avatar.url
                    )

        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1222923566379696190/1223107315121782855/5000choyen_1.png?ex=6618a674&is=66063174&hm=1d07cc1b74f4872cff500aecd85ecb488725c0260b46d4b2f1dec4d8636741b3&") # サムネイルとして小さい画像を設定できる

        embed.add_field(name="**//一般情報//**", inline=False, value=
                        f"> ** OS情報**\n"+
                        f"> [OS名] {platform.system()}\n"+
                        f"> [Architecture] {os_info.machine}\n> \n"+
                        
                        f"> **Python情報**\n"+
                        f"> [バージョン] {py_version}\n"+
                        f"> [ビルド日時] {py_buildDate}"
                        ) # フィールドを追加。
        embed.add_field(name="**//CPU情報//**", inline=False, value=
                        f"> [CPU名] {cpu_name}\n"+
                        f"> [コア数] {cpu_cores} Threads\n"+
                        f"> [周波数] {cpu_freq:.2f} GHz\n"+
                        f"> [使用率] {cpu_Load}%\n"
                        )
        embed.add_field(name="**//メモリ情報//**", value=
                        f"> [使用率] {(ram_info.used/1024/1024/1024):.2f}/{(ram_info.total/1024/1024/1024):.2f} GB"+
                        f" ({ram_info.percent}%)"
                        ) # フィールドを追加。
        embed.add_field(name="**//Yuranu情報(?)//**", inline=False, value=
                        f"> [OS] Yuranu 11 Pro\n"+
                        f"> [CPU使用率] {yuranu_cpu_load:.1f}%\n"+
                        f"> [メモリ使用率] {yuranu_mem_load:.2f}/{yuranu_maxmem:.2f}MB"+
                        f" ({((yuranu_mem_load/yuranu_maxmem)*100):.1f}%)\n"
                        ) # フィールドを追加。
        
        embed.set_footer(text="YuranuBot! | Made by yurq_",
                    icon_url=client.user.avatar.url)

        await interact.response.send_message(embed=embed)
        return
    
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)


rpc_case:int=0

async def performance(client: discord.Client):
    try:
        system = platform.system()

        while(True):
            for i in range(3): #メモリ使用率を表示する(2回更新)
                ram_info = psutil.virtual_memory()
                ram_total = ram_info.total/1024/1024/1024
                ram_used = ram_info.used/1024/1024/1024

                await client.change_presence(activity=discord.Game(f"RAM: {ram_used:.2f}/{ram_total:.2f}GB"))
                await asyncio.sleep(5)

            hard_id = 0
            cpu_Temp = psutil.sensors_temperatures()
            cpu_Load = psutil.cpu_percent()

            await client.change_presence(activity=discord.Game(f"CPU: {cpu_Load:.1f}% {cpu_Temp}℃"))
            await asyncio.sleep(5)

            await client.change_presence(activity=discord.Game(f"Python {platform.python_version()}"))
            await asyncio.sleep(5)

            await client.change_presence(activity=discord.Game(f"{system}に住んでいます"))

            await client.change_presence(activity=discord.Game(f"Use '/' to summon Zundamon"))
            await asyncio.sleep(5)

    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)

### 例外発生時に送信するチャンネルのIDを登録

async def sendException(e, filename, line_no):
    channel_myserv = client.get_channel(1222923566379696190)
    channel_sdev = client.get_channel(1223972040319696937)

    embed = discord.Embed( # Embedを定義する
                title="うまくいかなかったのだ。",# タイトル
                color=discord.Color.red(), # フレーム色指定(ぬーん神)
                description=f"例外エラーが発生しました！詳細はこちらをご覧ください。", # Embedの説明文 必要に応じて
                )
    embed.add_field(name="**//エラー内容//**", inline=False, value=
                    f"{filename}({line_no}行) -> [{type(e)}] {e}")
    
    await channel_myserv.send(embed=embed)
    # await channel_sdev.send(embed=embed)

load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")

# クライアント
client.run(BOT_TOKEN)
