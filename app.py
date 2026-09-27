from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from tradingview_ta import TA_Handler, Interval

app = Flask(__name__)
app.secret_key = 'quotex_ai_pro_ultimate_secure_2026'

VIP_PASSWORD = "VIP153"

FOREX_PAIRS = {
    'EUR/USD': 'EURUSD',
    'GBP/USD': 'GBPUSD',
    'USD/JPY': 'USDJPY',
    'AUD/USD': 'AUDUSD',
    'USD/CAD': 'USDCAD',
    'USD/CHF': 'USDCHF',
    'NZD/USD': 'NZDUSD',
    'EUR/GBP': 'EURGBP',
    'EUR/JPY': 'EURJPY',
    'GBP/JPY': 'GBPJPY',
    'AUD/JPY': 'AUDJPY',
    'EUR/AUD': 'EURAUD'
}

def get_interval(tf_str):
    mapping = {
        '1m': Interval.INTERVAL_1_MINUTE,
        '5m': Interval.INTERVAL_5_MINUTES,
        '15m': Interval.INTERVAL_15_MINUTES,
        '30m': Interval.INTERVAL_30_MINUTES,
        '1h': Interval.INTERVAL_1_HOUR
    }
    return mapping.get(tf_str, Interval.INTERVAL_1_MINUTE)

@app.route('/')
def home():
    # ইউজার লগইন না করা থাকলে সরাসরি লগইন পেজে পাঠিয়ে দেবে
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template(
        'index.html', 
        pairs=FOREX_PAIRS, 
        is_vip=session.get('is_vip', False),
        username=session.get('username', 'Trader')
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        vip_pass = data.get('vip_pass', '').strip()

        if not username:
            return jsonify({'status': 'error', 'msg_bn': 'অনুগ্রহ করে আপনার নাম বা ইউজারনেম দিন।'})

        session['logged_in'] = True
        session['username'] = username
        
        if 'lifetime_signal_count' not in session:
            session['lifetime_signal_count'] = 0

        session['is_vip'] = (vip_pass == VIP_PASSWORD)
        return jsonify({'status': 'success', 'redirect': '/'})

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/verify-vip', methods=['POST'])
def verify_vip():
    data = request.get_json(silent=True) or {}
    if data.get('vip_pass', '').strip() == VIP_PASSWORD:
        session['is_vip'] = True
        return jsonify({'status': 'success', 'msg_bn': '🎉 অভিনন্দন! আপনার VIP পাসওয়ার্ড সফলভাবে ভেরিফাই হয়েছে।'})
    else:
        return jsonify({'status': 'invalid', 'msg_bn': '❌ ভুল VIP পাসওয়ার্ড!'})

@app.route('/analyze', methods=['POST'])
def analyze():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'msg_bn': 'অনুগ্রহ করে প্রথমে লগইন করুন।'})

    is_vip = session.get('is_vip', False)
    lifetime_count = session.get('lifetime_signal_count', 0)

    if not is_vip and lifetime_count >= 5:
        return jsonify({
            'status': 'limit_reached',
            'msg_bn': 'আপনার ফ্রি ৫টি সিগন্যাল লিমিট শেষ! আনলিমিটেড সিগন্যালের জন্য VIP নিন।'
        })

    data = request.get_json(silent=True) or {}
    pair_symbol = data.get('pair')
    timeframe = data.get('timeframe', '5m')

    if not pair_symbol or pair_symbol not in FOREX_PAIRS:
        return jsonify({'status': 'error', 'msg_bn': 'সঠিক কারেন্সি পেয়ার নির্বাচন করুন।'})

    try:
        handler = TA_Handler(
            symbol=FOREX_PAIRS[pair_symbol],
            screener="forex",
            exchange="FX_IDC",
            interval=get_interval(timeframe)
        )
        analysis = handler.get_analysis()
        summary = analysis.summary
        indicators = analysis.indicators

        current_price = round(float(indicators.get('close', 0.0)), 5)
        ema_200 = round(float(indicators.get('EMA200', current_price)), 5)
        rsi = round(float(indicators.get('RSI', 50.0)), 2)
        
        buy_count = summary.get('BUY', 0)
        sell_count = summary.get('SELL', 0)
        rec = summary.get('RECOMMENDATION', 'NEUTRAL')

        is_uptrend = current_price > ema_200
        is_downtrend = current_price < ema_200

        if timeframe == '1m':
            expiry = "1 - 2 Minutes (Short Scalp)"
        elif timeframe == '5m':
            expiry = "5 - 10 Minutes (Standard Binary)"
        else:
            expiry = "15 - 30 Minutes (Swing Exp)"

        if ('BUY' in rec or buy_count > 15) and is_uptrend and rsi < 68:
            signal_title = "STRONG CALL 🟢 (UP)"
            action_code = "BUY"
            pa_zone = f"Support Reversal Zone: Wait for price to touch ~{round(current_price * 0.9996, 5)} then take **CALL (UP)**."
        elif ('SELL' in rec or sell_count > 15) and is_downtrend and rsi > 32:
            signal_title = "STRONG PUT 🔴 (DOWN)"
            action_code = "SELL"
            pa_zone = f"Resistance Rejection Zone: Wait for price to spike to ~{round(current_price * 1.0004, 5)} then take **PUT (DOWN)**."
        else:
            signal_title = "NEUTRAL ⚪ (WAIT)"
            action_code = "NEUTRAL"
            pa_zone = "Market consolidation. Wait for breakout at key resistance/support."
            expiry = "N/A"

        if not is_vip:
            session['lifetime_signal_count'] = lifetime_count + 1

        remaining = "আনলিমিটেড (VIP)" if is_vip else f"{5 - session['lifetime_signal_count']} টি বাকি"

        return jsonify({
            'status': 'success',
            'pair': pair_symbol,
            'signal_type': signal_title,
            'action_code': action_code,
            'entry_price': current_price,
            'pa_zone': pa_zone,
            'expiry': expiry,
            'timeframe': timeframe,
            'remaining': remaining,
            'msg_bn': '২৬+ ইন্ডিকেটর এবং প্রাইস অ্যাকশন জোন সফলভাবে যাচাই করা হয়েছে।'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'msg_bn': 'মার্কেট ডেটা ফেচ করতে ত্রুটি হয়েছে।'})

@app.route('/check-result', methods=['POST'])
def check_result():
    data = request.get_json(silent=True) or {}
    pair_symbol = data.get('pair')
    entry_price = float(data.get('entry_price', 0))
    action_code = data.get('action_code')
    timeframe = data.get('timeframe', '5m')

    if not pair_symbol or pair_symbol not in FOREX_PAIRS:
        return jsonify({'status': 'error', 'msg_bn': 'ইনভ্যালিড পেয়ার'})

    try:
        handler = TA_Handler(
            symbol=FOREX_PAIRS[pair_symbol],
            screener="forex",
            exchange="FX_IDC",
            interval=get_interval(timeframe)
        )
        indicators = handler.get_analysis().indicators
        exit_price = round(float(indicators.get('close', entry_price)), 5)

        is_win = False
        if action_code == 'BUY':
            is_win = exit_price >= entry_price
        elif action_code == 'SELL':
            is_win = exit_price <= entry_price

        result_text = "WIN 🟢 (সফল ট্রেড)" if is_win else "LOSS 🔴 (লস ট্রেড)"
        color_code = "#2ea043" if is_win else "#f85149"

        return jsonify({
            'status': 'success',
            'is_win': is_win,
            'result_text': result_text,
            'color_code': color_code,
            'entry_price': entry_price,
            'exit_price': exit_price
        })
    except Exception as e:
        return jsonify({'status': 'error', 'msg_bn': 'রেজাল্ট যাচাই করতে সমস্যা হয়েছে।'})

if __name__ == '__main__':
    app.run(debug=True)
