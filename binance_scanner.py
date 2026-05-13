import requests
import time
from datetime import datetime, timedelta

BASE_URL = "https://fapi.binance.com"

# ================== Render.com 환경변수로 설정 ==================
TELEGRAM_TOKEN = os.getenv('8532212383:AAF4r-wmg45tJ9p9JrR1_8_9R-jNo6EHe44')
TELEGRAM_CHAT_ID = os.getenv('7289039568')

notified_coins = {}

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        print("✅ 알림 전송")
    except Exception as e:
        print(f"❌ 알림 실패: {e}")

def get_30m_price_change(symbol):
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval=30m&limit=3", timeout=10)
        data = r.json()
        if len(data) >= 2:
            old = float(data[-2][4])
            new = float(data[-1][4])
            return (new - old) / old * 100
        return 0
    except:
        return 0

def get_1h_oi_change(symbol):
    try:
        r = requests.get(f"{BASE_URL}/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=2", timeout=8)
        data = r.json()
        if len(data) >= 2:
            return (float(data[1]['sumOpenInterest']) - float(data[0]['sumOpenInterest'])) / float(data[0]['sumOpenInterest']) * 100
        return 0
    except:
        return 0

def get_ls_ratio_change(symbol):
    try:
        r = requests.get(f"{BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=3", timeout=8)
        data = r.json()
        if len(data) >= 2:
            current = float(data[-1]['longShortRatio'])
            prev = float(data[-2]['longShortRatio'])
            return (current - prev) / prev * 100 if prev != 0 else 0
        return 0
    except:
        return 0

def get_funding_rate(symbol):
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/fundingRate?symbol={symbol}&limit=1", timeout=8)
        return float(r.json()[0]['fundingRate']) * 100
    except:
        return 0

def get_recent_high_low(symbol):
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval=15m&limit=20", timeout=10)
        data = r.json()
        highs = [float(c[2]) for c in data]
        lows = [float(c[3]) for c in data]
        return max(highs), min(lows)
    except:
        return None, None

def scan_bubble_scalper():
    try:
        resp = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=15)
        symbols = [s['symbol'] for s in resp.json()['symbols'] 
                   if s.get('contractType') == 'PERPETUAL' and s.get('quoteAsset') == 'USDT']
        
        print(f"🫧 버블스캐너 L/S보조필터 시작... (총 {len(symbols)}개)")
        
        for i, sym in enumerate(symbols):
            try:
                now = datetime.now()
                if sym in notified_coins and now - notified_coins[sym] < timedelta(minutes=20):
                    continue
                
                price_30m = get_30m_price_change(sym)
                oi_1h = get_1h_oi_change(sym)
                ls_change = get_ls_ratio_change(sym)
                funding = get_funding_rate(sym)
                
                # ================== 점수 계산 ==================
                price_score = 0
                oi_score = 0
                ls_score = 0
                funding_score = 0
                
                if price_30m > 3.2: price_score = 32
                elif price_30m > 2.0: price_score = 20
                elif price_30m > 1.0: price_score = 10
                
                if oi_1h > 7: oi_score = 25
                elif oi_1h > 4: oi_score = 15
                elif oi_1h > 2.5: oi_score = 8
                
                if ls_change < -3.2: ls_score = 25
                elif ls_change < -1.3: ls_score = 12
                if ls_change > 3.2: ls_score = -25
                elif ls_change > 1.3: ls_score = -12
                
                if 0.01 < funding < 0.075: funding_score = 10
                
                long_score = price_score + oi_score + max(ls_score, 0) + max(funding_score, 0)
                short_score = price_score + oi_score + max(-ls_score, 0) + max(-funding_score, 0)
                
                total = max(long_score, short_score)
                
                if total >= 55:
                    if long_score >= short_score + 10:
                        direction_emoji = "🟢"
                        direction_text = "🔥 강력 LONG 추천" if long_score >= 70 else "LONG 추천"
                    elif short_score >= long_score + 10:
                        direction_emoji = "🔴"
                        direction_text = "🔥 강력 SHORT 추천" if short_score >= 70 else "SHORT 추천"
                    else:
                        direction_emoji = "⚪"
                        direction_text = "중립"
                    
                    high, low = get_recent_high_low(sym)
                    target1 = target2 = "N/A"
                    if high and low:
                        rng = abs(high - low)
                        if direction_emoji == "🟢":
                            target1 = round(current_price + rng * 0.8, 4)
                            target2 = round(current_price + rng * 1.618, 4)
                        else:
                            target1 = round(current_price - rng * 0.8, 4)
                            target2 = round(current_price - rng * 1.618, 4)
                    
                    msg = f"""🫧 **버블스캐너 L/S보조필터**

**{sym}** {direction_emoji} **{direction_text}**

**총점: {total}점**

📈 가격 (30분): `{round(price_30m,2)}%`
📊 OI (1시간): `{round(oi_1h,2)}%`

🎯 **1차 타겟**: `{target1}`
🎯 **2차 타겟**: `{target2}`

⚠️ 15분봉 기준 • 단타 보조"""
                    
                    send_telegram(msg)
                    notified_coins[sym] = now
                    
                if (i + 1) % 50 == 0:
                    print(f"진행률: {i+1}/{len(symbols)}")
                
                time.sleep(0.05)
                
            except:
                continue
                
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    print("🫧 버블스캐너 L/S보조필터 Render 시작")
    send_telegram("✅ *Render.com에서 버블스캐너 L/S보조필터가 시작되었습니다!*")
    
    while True:
        scan_bubble_scalper()
        time.sleep(600)