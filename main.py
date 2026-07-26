import time
import requests
import pandas as pd
import numpy as np
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER $0 ÜCRETSİZ KATMAN İÇİN WEB SUNUCU ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TEEML Bot Is Live!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# ==========================================
# 1. TEEML BOT AYARLARI
# ==========================================
TELEGRAM_BOT_TOKEN = "8988063424:AAHFF6svlMtLkEo6Layi_3JS1bnQ2KfRc2I"
TELEGRAM_CHAT_ID = "8244530561"
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"  # 1 Dakikalık Test Periyodu

# Yeni Risk Ayarların
ATR_CARPANI = 1.0
RR_ORANI = 5.0

last_processed_time = None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        print(f"📩 Telegram Yanıtı: {res.status_code} - {res.text}", flush=True)
    except Exception as e:
        print("❌ Telegram Gönderim Hatası:", e, flush=True)

def fetch_klines(symbol, interval, limit=300):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        if not isinstance(res, list):
            print(f"⚠️ Binance Yanıtı Beklenen Format Değil: {res}", flush=True)
            return pd.DataFrame()
            
        df = pd.DataFrame(res, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        print("⚠️ Veri Çekme Hatası:", e, flush=True)
        return pd.DataFrame()

def calculate_strategy(df):
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr14'] = tr.rolling(window=14).mean()
    
    return df

print("🚀 TEEML Sinyal Botu Başlatıldı...", flush=True)
send_telegram("🚀 *TEEML Sinyal Botu Aktif!*\nParite: " + SYMBOL + "\nPeriyot: " + TIMEFRAME)

while True:
    try:
        df = fetch_klines(SYMBOL, TIMEFRAME)
        
        # Veri kontrolü (Boşsa veya yetersizse atla)
        if df.empty or len(df) < 200:
            time.sleep(10)
            continue
            
        df = calculate_strategy(df)
        
        last_bar = df.iloc[-2]
        bar_time = last_bar['time']
        
        if bar_time != last_processed_time:
            close = last_bar['close']
            open_p = last_bar['open']
            ema = last_bar['ema200']
            vol = last_bar['volume']
            vol_sma = last_bar['vol_sma20']
            atr = last_bar['atr14']
            
            long_sart = (close > ema) and (vol > vol_sma) and (close > open_p)
            short_sart = (close < ema) and (vol > vol_sma) and (close < open_p)
            
            if long_sart:
                stop_mesafesi = atr * ATR_CARPANI
                sl = close - stop_mesafesi
                tp = close + (stop_mesafesi * RR_ORANI)
                
                msg = f"🟢 *TEEML AL SİNYALİ*\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {close:.2f}\n" \
                      f"*Kar Al (TP):* {tp:.2f}\n" \
                      f"*Zarar Kes (SL):* {sl:.2f}"
                
                send_telegram(msg)
                last_processed_time = bar_time
                
            elif short_sart:
                stop_mesafesi = atr * ATR_CARPANI
                sl = close + stop_mesafesi
                tp = close - (stop_mesafesi * RR_ORANI)
                
                msg = f"🔴 *TEEML SAT SİNYALİ*\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {close:.2f}\n" \
                      f"*Kar Al (TP):* {tp:.2f}\n" \
                      f"*Zarar Kes (SL):* {sl:.2f}"
                
                send_telegram(msg)
                last_processed_time = bar_time
                
    except Exception as e:
        print("❌ Hata oluştu:", e, flush=True)
        
    time.sleep(10)
