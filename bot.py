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
import wave
import voicevox_core
from voicevox_core import AccelerationMode, AudioQuery, VoicevoxCore
from discord.player import FFmpegOpusAudio
from collections import deque, defaultdict
from dotenv import load_dotenv
import os
import re
import time
import threading
from database import db_load, get_db_setting, set_db_setting

ROOT_DIR = os.path.dirname(__file__)
SCRSHOT = os.path.join(ROOT_DIR, "scrshot", "scr.png")

### ロギングを開始
logging.basicConfig(level=logging.DEBUG)

###データベースの読み込み
db_data = db_load("database.db")

if db_data==False:
    logging.warn("データベースの読み込みに失敗しました")

### インテントの生成
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
logging.debug("discord.py -> インテント生成完了")

### クライアントの生成
client = discord.Client(intents=intents, activity=discord.Game(name="起きようとしています..."))
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
        
        ##接続を知らせるメッセージを送信
        channel_id = get_db_setting(db_data[0], interact.guild_id, "speak_channel")
        channel = discord.utils.get(interact.guild.channels, id=channel_id)
        length_limit = get_db_setting(db_data[0], interact.guild_id, "length_limit")
        yomiage_speed = get_db_setting(db_data[0], interact.guild_id, "speak_speed")
        
        if length_limit is None:
            set_db_setting(db_data[0], db_data[1], interact.guild_id, "length_limit", 80) ##文字数制限が設定されていない場合は新しく設定する
            length_limit = 80

        if yomiage_speed is None:
            set_db_setting(db_data[0], db_data[1], interact.guild_id, "speak_speed", 1) ##文字数制限が設定されていない場合は新しく設定する
            yomiage_speed = 1.0

        if length_limit == 0:
            length_limit = f"!!文字数制限なし!!"
        else:
            length_limit = f"{length_limit}文字"

        embed = discord.Embed(
            title="接続したのだ！",
            description="ずんだもんが楽しそうに読み上げてくれるって！",
            color=discord.Color.green()
        )
        embed.add_field(
            name="読み上げるチャンネル",
            value=channel
        )
        embed.add_field(
            name="読み上げ文字数の制限",
            value=length_limit,
            inline=False
        )
        embed.add_field(
            name="読み上げスピード",
            value=yomiage_speed,
            inline=False
        )
        embed.add_field(
            name="**VOICEVOXを使用しています！**",
            value="**[VOICEVOX、音声キャラクターの利用規約](<https://voicevox.hiroshiba.jp/>)を閲覧のうえ、正しく使うのだ！**",
            inline=False
        )

        embed.set_footer(text="YuranuBot! | Made by yurq_", icon_url=client.user.avatar.url)

        await interact.response.send_message(embed=embed)
        await yomiage_filter("接続したのだ。", interact.guild, 1)

    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)


@tree.command(name="yomiage-length-limit", description="読み上げる文字数を制限するのだ<<0で無効化するのだ！>>")
async def yomiage_length_limit(interact: discord.Interaction, length: int):
    try:
        result = set_db_setting(db_data[0], db_data[1], interact.guild_id, "length_limit", length)
        if result is None:
            await interact.response.send_message(f"☑読み上げ制限を**「{length}文字」**に設定したのだ！")
            return
        await interact.response.send_message(f"設定に失敗したのだ...")

    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)


@tree.command(name="yomiage-channel", description="読み上げるチャンネルを変更するのだ")
async def yomiage_channel(interact: discord.Interaction, channel: discord.TextChannel):
    try:
        result = set_db_setting(db_data[0], db_data[1], interact.guild_id, "speak_channel", channel.id)
        if result is None:
            await interact.response.send_message(f"☑**「{channel}」**を読み上げるのだ！")
            return
        await interact.response.send_message(f"設定に失敗したのだ...")

    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)


@tree.command(name="yomiage-speed", description="読み上げの速度を変更するのだ")
async def yomiage_speed(interact: discord.Interaction, speed: float):
    try:
        read_type = "speak_speed"
        result = set_db_setting(db_data[0], db_data[1], interact.guild_id, read_type, speed)

        if result is None:
            data = get_db_setting(db_data[0], interact.guild_id, read_type)
            await interact.response.send_message(f"読み上げ速度を**「{data}」**に変更したのだ！")
            return
        
        await interact.response.send_message("エラーが発生したのだ...")

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
                    if (member.nick is not None):##ギルド内のニックネームを読み上げる
                        await yomiage_filter(f"{member.nick}が参加したのだ。", member.guild, 3)
                    else:
                        await yomiage_filter(f"{member.name}が参加したのだ。", member.guild, 3)
                
            ##退席時に読み上げる
            if before.channel is not None:
                if (before.channel.id == bot_client.channel.id):
                    if member.nick is not None:
                        await yomiage_filter(f"{member.nick}が退席したのだ。", member.guild, 3)
                    else:
                        await yomiage_filter(f"{member.name}が退席したのだ。", member.guild, 3)

@client.event ##読み上げ用のイベント
async def on_message(message: discord.Message):
    if (message.guild.voice_client is None): ##ギルド内に接続していない場合は無視
        return
    
    if message.author.bot: ##ボットの内容は読み上げない
        return
    
    channel = get_db_setting(db_data[0], message.guild.id, "speak_channel") ##読み上げるチャンネルをデータベースから取得

    if (channel is None):
        embed = discord.Embed(
            color=discord.Color.red(),
            title="読み上げるチャンネルがわからないのだ...",
            description="読み上げを開始するには読み上げるチャンネルを設定してください！"
        )
        await message.channel.send(embed=embed)
        return
    
    if (message.channel.id == channel): ##ChannelIDが読み上げ対象のIDと一致しているか
        await yomiage_filter(message, message.guild, 3) ##難なくエラーをすり抜けたチャンネルにはもれなく読み上げ

yomiage_serv_list = defaultdict(deque)

## VOICEVOX用の設定
VC_OUTPUT = "./yomiage_data/"
FS = 24000

##ディレクトリがない場合は作成する
if (not os.path.isdir(VC_OUTPUT)):
    os.mkdir(VC_OUTPUT)
    

##読み上げのキューに入れる前に特定ワードを変換します
async def yomiage_filter(content, guild: discord.Guild, spkID: int):
    fix_words = [r'(https?://\S+)', r'<:[a-zA-Z0-9_]+:[0-9]+>', f"(ﾟ∀ﾟ)"]
    fix_end_word = ["URL", "えもじ", ""]
    
    ##メンションされたユーザーのIDを名前に変換
    if isinstance(content, discord.message.Message):
        fixed_content = content.content
        for mention in content.mentions:
            mention_id = mention.id
            mention_user = mention.name
            fixed_content = fixed_content.replace(f'<@{mention_id}>', mention_user)

    elif isinstance(content, str):
        fixed_content = content
        
    ##fix_wordに含まれたワードをfix_end_wordに変換する
    for i in range(len(fix_words)): 
        fixed_content = re.sub(fix_words[i], fix_end_word[i], fixed_content)
    
    length_limit = get_db_setting(db_data[0], guild.id, "length_limit")

    if (length_limit > 0): ##文字数制限(1文字以上なら有効化)
        speak_content = fixed_content[:length_limit] ##文字数制限（省略もつけちゃうよ♡）
    else:
        speak_content = fixed_content

    if (speak_content != fixed_content):
        speak_content = speak_content + "、省略なのだ"

    await queue_yomiage(speak_content, guild, spkID)

async def queue_yomiage(content: str, guild: discord.Guild, spkID: int):    
    try:
        ##サーバーごとに利用される速度のデータを取得
        speed = get_db_setting(db_data[0], guild.id, "speak_speed")

        ###読み上げ用のコアをロードし、作成します
        core = VoicevoxCore(
            acceleration_mode=AccelerationMode.AUTO,
            open_jtalk_dict_dir = './voicevox/open_jtalk_dic_utf_8-1.11'
        )
        core.load_model(spkID)

        audio_query = core.audio_query(content, spkID)
        audio_query.speed_scale = speed
        
        wav = core.synthesis(audio_query, spkID)

        wav_time = time.time() ##作成した時間を入れる
        voice_file = f"{VC_OUTPUT}{guild.id}-{wav_time}.wav"

        with wave.open(voice_file, "w") as wf:
            wf.setnchannels(1)  # チャンネル数の設定 (1:mono, 2:stereo)
            wf.setsampwidth(2)
            wf.setframerate(FS) 
            wf.writeframes(wav)  # ステレオデータを書きこむ
            
        with wave.open(voice_file,  'rb') as wr:\
            # 情報取得
            fr = wr.getframerate()
            fn = wr.getnframes()
            length = fn / fr

        file_list = [voice_file, length]

        queue = yomiage_serv_list[guild.id]
        queue.append(file_list)

        if not guild.voice_client.is_playing():
            send_voice(queue, guild.voice_client)
            
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        line_no = exception_traceback.tb_lineno
        logging.exception(f"読み上げ問題発生： {line_no}行目、 [{type(e)}] {e}")

def send_voice(queue, voice_client):
    
    if not queue or voice_client.is_playing():
        return
    
    source = queue.popleft()
    voice_client.play(FFmpegOpusAudio(source[0]), after=lambda e:send_voice(queue, voice_client))

    ##再生スタートが完了したら時間差でファイルを削除する。
    task = threading.Thread(target=delete_file_latency, args=(source[0], source[1]))
    task.start()

def delete_file_latency(file_name, latency):
    try:
        time.sleep(latency+2.0)
        os.remove(file_name)
        
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        line_no = exception_traceback.tb_lineno
        logging.exception(f"ファイル削除エラー： {line_no}行目、 [{type(e)}] {e}")



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
        
        temp_ = psutil.sensors_temperatures()
        if "coretemp" in temp_:
            for entry in temp_["coretemp"]:
                if entry.label == "Package id 0":
                    cpu_Temp = f"{entry.current}\u00B0C"

        ram_info = psutil.virtual_memory()
        
        py_version = platform.python_version()
        py_buildDate = platform.python_build()[1]

        ping = client.latency * 1000

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

        embed.set_thumbnail(url="https://www.iconsdb.com/icons/download/white/ok-128.png")

        embed.add_field(name="**//一般情報//**", inline=False, value=
                        f"> ** OS情報**\n"+
                        f"> [OS名] **{platform.system()}**\n"+
                        f"> [Architecture] **{os_info.machine}**\n> \n"+
                        
                        f"> **Python情報**\n"+
                        f"> [バージョン] **{py_version}**\n"+
                        f"> [ビルド日時] **{py_buildDate}**\n"+
                        f"> **Discord情報**\n"+
                        f"> [Discord.py] **Version {discord.__version__}**\n"+
                        f"> [Ping値] **{ping:.1f}ms**\n"
                        ) 
        embed.add_field(name="**//CPU情報//**", inline=False, value=
                        f"> [CPU名] **{cpu_name}**\n"+
                        f"> [コア数] **{cpu_cores} Threads**\n"+
                        f"> [周波数] **{cpu_freq:.2f} GHz**\n"+
                        f"> [使用率] **{cpu_Load}%**\n"+
                        f"> [温度] **{cpu_Temp}**"
                        )
        embed.add_field(name="**//メモリ情報//**", value=
                        f"> [使用率] **{(ram_info.used/1024/1024/1024):.2f}/{(ram_info.total/1024/1024/1024):.2f} GB"+
                        f" ({ram_info.percent}%)**"
                        ) # フィールドを追加。
        embed.add_field(name="**//Yuranu情報(?)//**", inline=False, value=
                        f"> [OS] **Yuranu 11 Pro**\n"+
                        f"> [CPU使用率] **{yuranu_cpu_load:.1f}%**\n"+
                        f"> [メモリ使用率] **{yuranu_mem_load:.2f}/{yuranu_maxmem:.2f}MB"+
                        f" ({((yuranu_mem_load/yuranu_maxmem)*100):.1f}%)**\n"
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

            for i in range(3):
                temp_ = psutil.sensors_temperatures()
                cpu_Temp = ""
                if "coretemp" in temp_:
                    for entry in temp_["coretemp"]:
                        if entry.label == "Package id 0":
                            cpu_Temp = f"Temp: {entry.current}\u00B0C"

                cpu_Load = psutil.cpu_percent()

                await client.change_presence(activity=discord.Game(f"CPU: {cpu_Load:.1f}%  {cpu_Temp}"))
                await asyncio.sleep(5)

            await client.change_presence(activity=discord.Game(f"Python {platform.python_version()}"))
            await asyncio.sleep(5)

            await client.change_presence(activity=discord.Game(f"{system}に住んでいます"))
            await asyncio.sleep(5)
            
            await client.change_presence(activity=discord.Game(f"ずんだもんは健康です！"))
            await asyncio.sleep(5)

    except Exception as e:        
        await client.change_presence(activity=discord.Game(f"RPCエラー: 要報告"))
        exception_type, exception_object, exception_traceback = sys.exc_info()
        filename = exception_traceback.tb_frame.f_code.co_filename
        line_no = exception_traceback.tb_lineno
        await sendException(e, filename, line_no)
        
        await asyncio.sleep(5)
        task = asyncio.create_task(performance(client))

### 例外発生時に送信するチャンネルのIDを登録

async def sendException(e, filename, line_no):
    channel_myserv = client.get_channel(1222923566379696190)
    channel_sdev = client.get_channel(1223972040319696937)

    if (type(e) == voicevox_core.VoicevoxError): ##読み上げできない文章はエラーを無視する
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
