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
TIMEFRAME = "1m"

# Risk Ayarların
ATR_CARPANI = 1.0
RR_ORANI = 5.0

# İşlem Takip Değişkenleri (Hafıza)
active_position = None  # None, 'LONG', 'SHORT'
entry_price = 0.0
tp_price = 0.0
sl_price = 0.0
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
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api2.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    ]
    
    for url in endpoints:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=5).json()
            if isinstance(res, list) and len(res) > 0:
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
        except Exception:
            continue
            
    print("⚠️ Tüm Binance endpointleri başarısız oldu.", flush=True)
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

print("🚀 TEEML Akıllı Pozisyon Takip Botu Başlatıldı...", flush=True)
send_telegram("🚀 *TEEML Sinyal Botu Aktif!*\nParite: " + SYMBOL + "\nPeriyot: " + TIMEFRAME)

while True:
    try:
        df = fetch_klines(SYMBOL, TIMEFRAME)
        
        if df.empty or len(df) < 200:
            time.sleep(5)
            continue
            
        df = calculate_strategy(df)
        
        current_candle = df.iloc[-1]
        current_high = current_candle['high']
        current_low = current_candle['low']
        
        # ----------------------------------------------------
        # 1. AKTİF POZİSYON KONTROLÜ (TP / SL ULAŞILDI MI?)
        # ----------------------------------------------------
        if active_position == 'LONG':
            if current_high >= tp_price:
                msg = f"🎯 *BAŞARILI: KAR AL (TP) OLUNDU!* 🟢\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                      f"*Hedef TP:* {tp_price:.2f}\n" \
                      f"*Gerçekleşen Yüksek:* {current_high:.2f}\n\n" \
                      f"✅ *Pozisyon kârla kapatıldı. Yeni sinyal taranıyor...*"
                send_telegram(msg)
                active_position = None  # Pozisyonu kapat, yeni sinyale izin ver
                
            elif current_low <= sl_price:
                msg = f"🛑 *BAŞARISIZ: ZARAR KES (SL) OLUNDU!* 🔴\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                      f"*Stop SL:* {sl_price:.2f}\n" \
                      f"*Gerçekleşen Düşük:* {current_low:.2f}\n\n" \
                      f"⚠️ *Pozisyon zararla kapatıldı. Yeni sinyal taranıyor...*"
                send_telegram(msg)
                active_position = None  # Pozisyonu kapat, yeni sinyale izin ver

        elif active_position == 'SHORT':
            if current_low <= tp_price:
                msg = f"🎯 *BAŞARILI: KAR AL (TP) OLUNDU!* 🟢\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                      f"*Hedef TP:* {tp_price:.2f}\n" \
                      f"*Gerçekleşen Düşük:* {current_low:.2f}\n\n" \
                      f"✅ *Pozisyon kârla kapatıldı. Yeni sinyal taranıyor...*"
                send_telegram(msg)
                active_position = None  # Pozisyonu kapat, yeni sinyale izin ver
                
            elif current_high >= sl_price:
                msg = f"🛑 *BAŞARISIZ: ZARAR KES (SL) OLUNDU!* 🔴\n\n" \
                      f"*Parite:* {SYMBOL}\n" \
                      f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                      f"*Stop SL:* {sl_price:.2f}\n" \
                      f"*Gerçekleşen Yüksek:* {current_high:.2f}\n\n" \
                      f"⚠️ *Pozisyon zararla kapatıldı. Yeni sinyal taranıyor...*"
                send_telegram(msg)
                active_position = None  # Pozisyonu kapat, yeni sinyale izin ver

        # ----------------------------------------------------
        # 2. YENİ SİNYAL TARAMASI (Sadece Aktif Pozisyon Yoksa)
        # ----------------------------------------------------
        if active_position is None:
            last_closed_bar = df.iloc[-2]
            bar_time = last_closed_bar['time']
            
            if bar_time != last_processed_time:
                close = last_closed_bar['close']
                open_p = last_closed_bar['open']
                ema = last_closed_bar['ema200']
                vol = last_closed_bar['volume']
                vol_sma = last_closed_bar['vol_sma20']
                atr = last_closed_bar['atr14']
                
                long_sart = (close > ema) and (vol > vol_sma) and (close > open_p)
                short_sart = (close < ema) and (vol > vol_sma) and (close < open_p)
                
                if long_sart:
                    stop_mesafesi = atr * ATR_CARPANI
                    entry_price = close
                    sl_price = entry_price - stop_mesafesi
                    tp_price = entry_price + (stop_mesafesi * RR_ORANI)
                    active_position = 'LONG'
                    last_processed_time = bar_time
                    
                    msg = f"🟢 *TEEML YENİ AL SİNYALİ*\n\n" \
                          f"*Parite:* {SYMBOL}\n" \
                          f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                          f"*Kar Al (TP):* {tp_price:.2f}\n" \
                          f"*Zarar Kes (SL):* {sl_price:.2f}\n\n" \
                          f"⏳ *İşlem canlı takip ediliyor. TP veya SL olana kadar yeni sinyal atılmayacak.*"
                    send_telegram(msg)
                    
                elif short_sart:
                    stop_mesafesi = atr * ATR_CARPANI
                    entry_price = close
                    sl_price = entry_price + stop_mesafesi
                    tp_price = entry_price - (stop_mesafesi * RR_ORANI)
                    active_position = 'SHORT'
                    last_processed_time = bar_time
                    
                    msg = f"🔴 *TEEML YENİ SAT SİNYALİ*\n\n" \
                          f"*Parite:* {SYMBOL}\n" \
                          f"*Giriş Fiyatı:* {entry_price:.2f}\n" \
                          f"*Kar Al (TP):* {tp_price:.2f}\n" \
                          f"*Zarar Kes (SL):* {sl_price:.2f}\n\n" \
                          f"⏳ *İşlem canlı takip ediliyor. TP veya SL olana kadar yeni sinyal atılmayacak.*"
                    send_telegram(msg)

    except Exception as e:
        print("❌ Hata oluştu:", e, flush=True)
        
    time.sleep(5)
