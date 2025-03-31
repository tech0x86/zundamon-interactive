import time
import board
import pwmio
import RPi.GPIO as GPIO
import sys
import os
import json
import queue
import threading
import random
import requests
import pygame
from datetime import datetime, timedelta
import schedule

# OpenAI APIのキー（環境変数から取得するか、直接設定する）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "あなたのAPIキーをここに設定")

# VOICEVOX APIのエンドポイント（ローカルに立てるか、外部サービスを利用）
VOICEVOX_API_URL = "http://localhost:50021"  # ローカルサーバーの場合
VOICEVOX_SPEAKER_ID = 1  # ずんだもんのID

# ニュース検索用のAPI（例：NewsAPI）
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "あなたのニュースAPIキーをここに設定")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

# GPIOピンの設定
# PWM出力用に設定（LEDのRGB）
red_pin = pwmio.PWMOut(board.D16, frequency=1000, duty_cycle=0)
green_pin = pwmio.PWMOut(board.D20, frequency=1000, duty_cycle=0)
blue_pin = pwmio.PWMOut(board.D21, frequency=1000, duty_cycle=0)

# 超音波センサーの設定
trig_pin = 15  # GPIO 15
echo_pin = 14  # GPIO 14
speed_of_sound = 34370  # 20℃での音速(cm/s)

GPIO.setmode(GPIO.BCM)  # GPIOをBCMモードで使用
GPIO.setwarnings(False)  # GPIO警告無効化
GPIO.setup(trig_pin, GPIO.OUT)  # Trigピン出力モード設定
GPIO.setup(echo_pin, GPIO.IN)  # Echoピン入力モード設定

# Pygameの初期化（音声再生用）
pygame.mixer.init()

# グローバル変数
audio_queue = queue.Queue()  # 音声再生キュー
news_data = []  # ニュースデータ保存用
last_news_update = datetime.now() - timedelta(days=1)  # 前回ニュース更新時間
last_interaction_time = 0  # 最後の対話時間
conversation_history = []  # 会話履歴
emotion_state = "normal"  # 感情状態（normal, happy, angry, sad, surprised）

# ディレクトリ作成
os.makedirs("audio_cache", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# LEDの明るさを設定する関数
def set_led_color(r, g, b):
    """LEDの色を設定します。
    Args:
        r (int): 赤色の明るさ (0～65535)。
        g (int): 緑色の明るさ (0～65535)。
        b (int): 青色の明るさ (0～65535)。
    """
    red_pin.duty_cycle = r
    green_pin.duty_cycle = g
    blue_pin.duty_cycle = b

# 超音波センサーで距離を取得する関数
def get_distance():
    GPIO.output(trig_pin, GPIO.HIGH)
    time.sleep(0.000010)
    GPIO.output(trig_pin, GPIO.LOW)

    while not GPIO.input(echo_pin):
        pass
    t1 = time.time()

    while GPIO.input(echo_pin):
        pass
    t2 = time.time()

    return (t2 - t1) * speed_of_sound / 2

# 感情に合わせたLEDセット
def set_emotion_led(emotion):
    global emotion_state
    emotion_state = emotion
    
    if emotion == "normal":
        set_led_color(32767, 32767, 32767)  # 白色
    elif emotion == "happy":
        set_led_color(0, 65535, 0)  # 緑色
    elif emotion == "angry":
        set_led_color(65535, 0, 0)  # 赤色
    elif emotion == "sad":
        set_led_color(0, 0, 65535)  # 青色
    elif emotion == "surprised":
        set_led_color(65535, 65535, 0)  # 黄色

# 口パク表現（LEDの点滅で簡易表現）
def lip_sync(duration):
    original_emotion = emotion_state
    for _ in range(int(duration * 2)):  # 口パク頻度を調整
        # LEDを一瞬だけ暗くして口パク表現
        set_led_color(0, 0, 0)
        time.sleep(0.1)
        # 元の感情の色に戻す
        set_emotion_led(original_emotion)
        time.sleep(0.15)

# VOICEVOXで音声生成
def generate_voice(text, speaker_id=VOICEVOX_SPEAKER_ID):
    """VOICEVOXを使用して音声を生成し、ファイルパスを返します。"""
    # キャッシュファイル名生成（テキストのハッシュ値を使用）
    cache_filename = f"audio_cache/{hash(text)}.wav"
    
    # キャッシュが存在すればそれを返す
    if os.path.exists(cache_filename):
        return cache_filename
    
    try:
        # 音声合成クエリの作成
        params = {"text": text, "speaker": speaker_id}
        query_response = requests.post(
            f"{VOICEVOX_API_URL}/audio_query", 
            params=params
        )
        query_response.raise_for_status()
        query_data = query_response.json()
        
        # 音声合成
        synthesis_response = requests.post(
            f"{VOICEVOX_API_URL}/synthesis", 
            headers={"Content-Type": "application/json"},
            params={"speaker": speaker_id},
            data=json.dumps(query_data)
        )
        synthesis_response.raise_for_status()
        
        # 音声ファイル保存
        with open(cache_filename, "wb") as f:
            f.write(synthesis_response.content)
        
        return cache_filename
    
    except Exception as e:
        print(f"音声生成エラー: {e}")
        return None

# 音声再生スレッド
def audio_player_thread():
    while True:
        audio_file = audio_queue.get()
        if audio_file is None:
            continue
        
        try:
            # 音声ファイルの長さを取得（口パク用）
            sound = pygame.mixer.Sound(audio_file)
            duration = sound.get_length()
            
            # 音声再生
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            # 口パク表現を同時実行
            lip_sync_thread = threading.Thread(target=lip_sync, args=(duration,))
            lip_sync_thread.start()
            
            # 再生終了まで待機
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
        except Exception as e:
            print(f"音声再生エラー: {e}")
        
        finally:
            audio_queue.task_done()

# LLMで応答生成
def generate_response(prompt, model="gpt-3.5-turbo"):
    """OpenAI APIを使用して応答を生成します。"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "あなたはずんだもんというキャラクターです。「～のだ」「～なのだ」という語尾で話し、かわいくて元気な女の子のような口調で話します。一人称は「ボク」です。短く、簡潔な応答を心がけてください。"},
                *conversation_history[-5:],  # 最新5件の会話履歴を含める
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(data)
        )
        response.raise_for_status()
        result = response.json()
        
        # 応答を取得
        message = result["choices"][0]["message"]["content"].strip()
        
        # 会話履歴に追加
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": message})
        
        # 感情を分析
        analyze_emotion(message)
        
        return message
    
    except Exception as e:
        print(f"応答生成エラー: {e}")
        return "エラーが発生したのだ。ごめんなさいなのだ。"

# 感情分析
def analyze_emotion(text):
    """テキストから感情を推測して、LEDの色を変更します。"""
    try:
        # 簡易的な感情分析（キーワードベース）
        if any(word in text for word in ["嬉しい", "楽しい", "やったー", "！！", "わーい"]):
            set_emotion_led("happy")
        elif any(word in text for word in ["怒", "むかっ", "許さない", "ひどい"]):
            set_emotion_led("angry")
        elif any(word in text for word in ["悲しい", "さみしい", "泣", "つらい"]):
            set_emotion_led("sad")
        elif any(word in text for word in ["びっくり", "えっ", "まさか", "驚"]):
            set_emotion_led("surprised")
        else:
            set_emotion_led("normal")
    except Exception as e:
        print(f"感情分析エラー: {e}")
        set_emotion_led("normal")

# ニュース取得
def fetch_news():
    """NewsAPIからニュースを取得します。"""
    global news_data, last_news_update
    
    try:
        params = {
            "country": "jp",
            "apiKey": NEWS_API_KEY,
            "pageSize": 10
        }
        
        response = requests.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        result = response.json()
        
        if result["status"] == "ok" and result["articles"]:
            news_data = result["articles"]
            last_news_update = datetime.now()
            print(f"ニュース更新: {len(news_data)}件取得")
            return True
        
    except Exception as e:
        print(f"ニュース取得エラー: {e}")
    
    return False

# ランダムニュースの話題提供
def get_random_news_topic():
    """取得したニュースからランダムに一つ選び、トピックとして返します。"""
    global news_data
    
    # ニュースデータが空か1日以上経過していたら更新
    if not news_data or (datetime.now() - last_news_update).days >= 1:
        fetch_news()
    
    if news_data:
        article = random.choice(news_data)
        title = article.get("title", "")
        return f"最近のニュースで「{title}」というのがあるのだ。これについてどう思うのだ？"
    
    return "最近面白いニュースはあるのかな？"

# アイドル時の話題提供
def get_idle_topic():
    """アイドル状態（人がいない時）の話題をランダムに提供します。"""
    topics = [
        "今日の天気はどうかな？",
        "何か面白いことがあったのだ？",
        "ボクはずんだもちが大好きなのだ！",
        "プログラミング楽しいのだ！",
        "何か質問があれば言ってほしいのだ",
    ]
    
    # 20%の確率でニュースを話題にする
    if random.random() < 0.2:
        return get_random_news_topic()
    
    return random.choice(topics)

# 人が接近したときの挨拶
def greeting_on_approach():
    """人が接近したときに使用する挨拶文をランダムに返します。"""
    greetings = [
        "こんにちはなのだ！ボクはずんだもんなのだ！",
        "わーい！お客さんが来たのだ！",
        "いらっしゃいなのだ！何かお手伝いできることはあるのだ？",
        "こんにちはなのだ！今日はいい天気なのだ！",
        "ずんだもんだよ！よろしくなのだ！"
    ]
    return random.choice(greetings)

# 定期的なニュース更新スケジュール設定
def schedule_news_updates():
    schedule.every(6).hours.do(fetch_news)

# メイン関数
def main():
    # 音声再生スレッドの開始
    audio_thread = threading.Thread(target=audio_player_thread, daemon=True)
    audio_thread.start()
    
    # ニュース更新スケジュール設定
    schedule_news_updates()
    
    # 初回ニュース取得
    fetch_news()
    
    global last_interaction_time
    idle_counter = 0
    
    # 初期状態設定
    set_emotion_led("normal")
    
    print("ずんだもん対話システム起動完了！")
    
    try:
        while True:
            # スケジュールタスク実行
            schedule.run_pending()
            
            # 距離取得
            distance = get_distance()
            current_time = time.time()
            
            # 人が近くにいる場合（1.5m以内）
            if distance < 150:
                # 前回の対話から30秒以上経過している場合
                if current_time - last_interaction_time > 30:
                    # 挨拶メッセージを生成
                    greeting = greeting_on_approach()
                    print(f"挨拶: {greeting}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(greeting)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
                
                # 50cm以内に近づいた場合はより積極的に会話
                elif distance < 50 and current_time - last_interaction_time > 10:
                    # ランダムな話題またはニュース
                    if random.random() < 0.3:  # 30%の確率でニュース
                        topic = get_random_news_topic()
                    else:
                        topic = get_idle_topic()
                    
                    print(f"話題提供: {topic}")
                    
                    # LLMで応答生成
                    response = generate_response(topic)
                    print(f"応答: {response}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(response)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
            
            # 人がいない場合のアイドル行動
            else:
                idle_counter += 1
                
                # 約10分ごとに独り言（600秒 ÷ 0.1秒のスリープ = 6000）
                if idle_counter >= 6000:
                    idle_topic = get_idle_topic()
                    idle_response = generate_response(f"独り言: {idle_topic}")
                    print(f"独り言: {idle_response}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(idle_response)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    idle_counter = 0
            
            # 少し待機
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("プログラムを終了します。")
    
    finally:
        # 終了処理
        GPIO.cleanup()
        set_led_color(0, 0, 0)
        sys.exit()

if __name__ == "__main__":
    main()