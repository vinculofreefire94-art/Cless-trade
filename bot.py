import telebot
import ccxt
import pandas as pd
import mplfinance as mpf
from tradingview_ta import TA_Handler, Interval
import feedparser
import schedule
import time
import threading
import random
import os
from datetime import datetime, timezone

TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '-1003780528406')

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

SYMBOL_TV   = 'BTCUSDT'
CCXT_SYMBOL = 'BTC/USDT'

ultimo_sinal        = None
ultimo_link_noticia = None
sinal_lock          = threading.Lock()

SABEDORIA = [
    '📜 <i>O mercado pune a ganancia e recompensa a paciencia.</i>',
    '📜 <i>O stop loss nao e fraqueza - e sobrevivencia.</i>',
    '📜 <i>O mercado e um espelho da psicologia humana. Domine a si mesmo.</i>',
    '📜 <i>A preservacao de capital e a primeira regra. Sem capital, nao ha jogo.</i>',
]

MOTIVACOES = [
    '💎 <b>O mercado transfere dinheiro dos impacientes para os pacientes.</b>',
    '🚀 <b>Traders amadores focam nos lucros. Profissionais focam em proteger o capital.</b>',
    '🦅 <b>A disciplina e a ponte entre a meta e a realizacao.</b>',
    '🔥 <b>Um dia ruim de trade nao define sua carreira. A consistencia, sim.</b>',
    '👑 <b>O sucesso no mercado e 20% estrategia e 80% psicologia.</b>',
]

def get_multi_currency_prices(base_asset='BTC'):
    exchange = ccxt.binance()
    try:
        tickers = exchange.fetch_tickers(
            [base_asset + '/USDT', base_asset + '/EUR', base_asset + '/USDC']
        )
        return {
            'USD':  tickers[base_asset + '/USDT']['last'],
            'EUR':  tickers[base_asset + '/EUR']['last'],
            'USDC': tickers[base_asset + '/USDC']['last'],
        }
    except Exception as e:
        print('[ERRO] Cotacoes: ' + str(e))
        return None

def get_tradingview_analysis(symbol=SYMBOL_TV, interval=Interval.INTERVAL_1_HOUR):
    try:
        handler = TA_Handler(
            symbol=symbol, screener='crypto',
            exchange='BINANCE', interval=interval
        )
        a = handler.get_analysis()
        return {
            'rec':          a.summary['RECOMMENDATION'],
            'rsi':          a.indicators.get('RSI', 50),
            'adx':          a.indicators.get('ADX', 20),
            'atr':          a.indicators.get('ATR', 0),
            'buy_signals':  a.summary.get('BUY', 0),
            'sell_signals': a.summary.get('SELL', 0),
        }
    except Exception as e:
        print('[ERRO] TradingView: ' + str(e))
        return None

def get_confluence_signal():
    tf1h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_1_HOUR)
    tf4h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_4_HOURS)
    if not tf1h or not tf4h:
        return None, tf1h
    
    def direction(rec):
        if 'BUY'  in rec: return 'BUY'
        if 'SELL' in rec: return 'SELL'
        return 'NEUTRAL'
    
    dir1h = direction(tf1h['rec'])
    dir4h = direction(tf4h['rec'])
    tf1h['tf4h_rec'] = tf4h['rec']
    
    if dir1h == dir4h and dir1h != 'NEUTRAL':
        tf1h['confluence'] = True
        return dir1h, tf1h
    
    tf1h['confluence'] = False
    return (dir1h if dir1h != 'NEUTRAL' else None), tf1h

def generate_premium_chart(symbol=CCXT_SYMBOL, timeframe='1h', limit=120):
    try:
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        
        df['EMA9']  = df['close'].ewm(span=9,  adjust=False).mean()
        df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        delta = df['close'].diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss  = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / loss))
        
        df['EMA12']  = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26']  = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD']   = df['EMA12'] - df['EMA26']
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist']   = df['MACD'] - df['Signal']
        
        colors_macd = ['#00E5A0' if v >= 0 else '#FF3D6B' for v in df['Hist']]
        
        mc = mpf.make_marketcolors(up='#00E5A0', down='#FF3D6B', edge='inherit', wick='inherit', volume='inherit')
        s  = mpf.make_mpf_style(
            marketcolors=mc, gridstyle=':', y_on_right=True,
            facecolor='#0B0E1A', edgecolor='#1E2440', figcolor='#0B0E1A',
            rc={'text.color': '#CDD6F4', 'axes.labelcolor': '#CDD6F4', 'xtick.color': '#CDD6F4', 'ytick.color': '#CDD6F4'}
        )
        
        apds = [
            mpf.make_addplot(df['EMA9'],   color='#F5C842', width=1.2, panel=0),
            mpf.make_addplot(df['EMA21'],  color='#4DA6FF', width=1.2, panel=0),
            mpf.make_addplot(df['EMA50'],  color='#FF8C42', width=1.0, panel=0, linestyle='–'),
            mpf.make_addplot(df['RSI'],    panel=2, color='#B06EFF', ylabel='RSI',  width=1.2),
            mpf.make_addplot([70]*len(df), panel=2, color='#FF3D6B', linestyle='–', width=0.8),
            mpf.make_addplot([30]*len(df), panel=2, color='#00E5A0', linestyle='–', width=0.8),
            mpf.make_addplot(df['MACD'],   panel=3, color='#4DA6FF', ylabel='MACD', width=1.2),
            mpf.make_addplot(df['Signal'], panel=3, color='#F5C842', width=1.2),
            mpf.make_addplot(df['Hist'],   type='bar', panel=3, color=colors_macd, alpha=0.6),
        ]
        
        fname = 'elite_chart_BTC.png'
        mpf.plot(df, type='candle', volume=True, style=s, addplot=apds,
                title='Bitcoin Institucional - Algoritmo Elite (1H)',
                savefig=fname, figsize=(14, 10), panel_ratios=(4, 1, 1.5, 1.5), tight_layout=True)
        return fname
    except Exception as e:
        print('[ERRO] Grafico: ' + str(e))
        return None

def send_trade_signal(force=False):
    global ultimo_sinal
    with sinal_lock:
        direction, tv_data = get_confluence_signal()
        prices = get_multi_currency_prices('BTC')
        
        if not tv_data or not prices or not direction:
            print('[INFO] Sem sinal direcional.')
            return
        
        is_buy     = direction == 'BUY'
        trade_type = 'COMPRA LONG' if is_buy else 'VENDA SHORT'
        
        if trade_type == ultimo_sinal and not force:
            print('[INFO] Sinal repetido.')
            return
        
        adx = tv_data['adx']
        if adx < 20 and not force:
            print('[INFO] ADX baixo. Descartado.')
            return
        
        ultimo_sinal = trade_type
        
        rsi        = tv_data['rsi']
        price_usd  = prices['USD']
        price_eur  = prices['EUR']
        price_usdc = prices['USDC']
        atr        = tv_data['atr'] if tv_data['atr'] else (price_usd * 0.015)
        confluence = tv_data.get('confluence', False)
        tf4h_rec   = tv_data.get('tf4h_rec', 'N/D')
        buy_sig    = tv_data.get('buy_signals', 0)
        sell_sig   = tv_data.get('sell_signals', 0)
        
        emoji       = '🟢' if is_buy else '🔴'
        chart_emoji = '📈' if is_buy else '📉'
        conf_badge  = 'CONFLUENCIA 1H+4H OK' if confluence else 'Sinal 1H apenas'
        
        mult_sl, mult_tp1, mult_tp2 = 1.5, 1.5, 3.0
        
        if is_buy:
            sl_usd  = price_usd - (atr * mult_sl)
            tp1_usd = price_usd + (atr * mult_tp1)
            tp2_usd = price_usd + (atr * mult_tp2)
        else:
            sl_usd  = price_usd + (atr * mult_sl)
            tp1_usd = price_usd - (atr * mult_tp1)
            tp2_usd = price_usd - (atr * mult_tp2)
        
        rr_tp1 = abs(tp1_usd - price_usd) / abs(sl_usd - price_usd)
        rr_tp2 = abs(tp2_usd - price_usd) / abs(sl_usd - price_usd)
        r_tp1  = tp1_usd / price_usd
        r_tp2  = tp2_usd / price_usd
        r_sl   = sl_usd  / price_usd
        
        adx_text = 'Forte' if adx > 25 else 'Moderado' if adx > 20 else 'Fraco'
        rsi_text = 'Sobrecomprado' if rsi > 70 else 'Sobrevendido' if rsi < 30 else 'Neutro'
        now_str  = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
        
        chart_file = generate_premium_chart()
        
        msg = (
            chart_emoji + ' <b>ALERTA INSTITUCIONAL ELITE</b> ' + chart_emoji + '\n'
            + '<code>================================</code>\n'
            + 'Hora: <i>' + now_str + '</i>\n'
            + 'Ativo: Bitcoin (BTC)\n'
            + emoji + ' Operacao: <code>' + trade_type + '</code>\n'
            + 'Analise: ' + conf_badge + '\n'
            + '<code>================================</code>\n'
            + 'ADX: ' + adx_text + ' (' + str(round(adx, 1)) + ')\n'
            + 'RSI: ' + rsi_text + ' (' + str(round(rsi, 1)) + ')\n'
            + 'Sinais 1H: ' + str(buy_sig) + ' compra / ' + str(sell_sig) + ' venda\n'
            + '4H: <code>' + tf4h_rec + '</code>\n'
            + '<code>================================</code>\n'
            + 'ENTRADA:\n'
            + '  USD:  <code>$' + '{:,.2f}'.format(price_usd)  + '</code>\n'
            + '  EUR:  <code>E' + '{:,.2f}'.format(price_eur)  + '</code>\n'
            + '  USDC: <code>'  + '{:,.2f}'.format(price_usdc) + '</code>\n'
            + '<code>================================</code>\n'
            + 'TP1 - R:R ' + str(round(rr_tp1, 1)) + ':1\n'
            + '  USD: <code>$' + '{:,.2f}'.format(tp1_usd) + '</code>\n'
            + 'TP2 - R:R ' + str(round(rr_tp2, 1)) + ':1\n'
            + '  USD: <code>$' + '{:,.2f}'.format(tp2_usd) + '</code>\n'
            + 'STOP LOSS:\n'
            + '  USD: <code>$' + '{:,.2f}'.format(sl_usd) + '</code>\n'
            + '<code>================================</code>\n'
            + 'Risco: max 1-2% do capital\n'
            + 'ATR: <code>$' + '{:,.2f}'.format(atr) + '</code>\n\n'
            + random.choice(SABEDORIA)
        )
        
        try:
            if chart_file and os.path.exists(chart_file):
                with open(chart_file, 'rb') as photo:
                    bot.send_photo(CHAT_ID, photo, caption=msg)
            else:
                bot.send_message(CHAT_ID, msg)
            print('[OK] Sinal: ' + trade_type)
        except Exception as e:
            print('[ERRO] Envio: ' + str(e))
        finally:
            if chart_file and os.path.exists(chart_file):
                os.remove(chart_file)

def send_crypto_news():
    global ultimo_link_noticia
    try:
        feed = feedparser.parse('https://cointelegraph.com.br/rss')
        for entry in feed.entries[:5]:
            if entry.link != ultimo_link_noticia:
                ultimo_link_noticia = entry.link
                summary = getattr(entry, 'summary', '')[:220]
                msg = (
                    '🌍 <b>RADAR DO MERCADO - ELITE NEWS</b>\n'
                    + '<code>================================</code>\n'
                    + '<b>' + entry.title + '</b>\n\n'
                    + '<i>' + summary + '…</i>\n\n'
                    + '<a href="' + entry.link + '">Ler materia completa</a>\n'
                    + '<code>================================</code>\n'
                    + random.choice(MOTIVACOES)
                )
                bot.send_message(CHAT_ID, msg, disable_web_page_preview=False)
                break
    except Exception as e:
        print('[ERRO] Noticias: ' + str(e))

@bot.message_handler(commands=['start', 'ajuda'])
def cmd_start(msg):
    bot.send_message(msg.chat.id,
        '<b>Bot Elite - Comandos:</b>\n\n'
        + '/btc    - Analise imediata\n'
        + '/news   - Ultima noticia\n'
        + '/status - Status do sistema\n'
        + '/ajuda  - Este menu'
    )

@bot.message_handler(commands=['btc'])
def cmd_btc(msg):
    bot.send_message(msg.chat.id, 'Gerando analise, aguarde…')
    threading.Thread(target=send_trade_signal, kwargs={'force': True}, daemon=True).start()

@bot.message_handler(commands=['news'])
def cmd_news(msg):
    bot.send_message(msg.chat.id, 'Buscando noticia…')
    threading.Thread(target=send_crypto_news, daemon=True).start()

@bot.message_handler(commands=['status'])
def cmd_status(msg):
    prices = get_multi_currency_prices('BTC')
    tv     = get_tradingview_analysis()
    now    = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
    if prices and tv:
        status = (
            'SISTEMA ONLINE - ' + now + '\n'
            + '<code>================================</code>\n'
            + 'BTC/USD:  <code>$' + '{:,.2f}'.format(prices['USD'])  + '</code>\n'
            + 'BTC/EUR:  <code>E' + '{:,.2f}'.format(prices['EUR'])  + '</code>\n'
            + 'BTC/USDC: <code>'  + '{:,.2f}'.format(prices['USDC']) + '</code>\n'
            + '<code>================================</code>\n'
            + 'RSI: <code>' + str(round(tv['rsi'], 1)) + '</code>\n'
            + 'ADX: <code>' + str(round(tv['adx'], 1)) + '</code>\n'
            + 'Resumo: <code>' + tv['rec'] + '</code>'
        )
    else:
        status = 'Erro ao obter dados.'
    bot.send_message(msg.chat.id, status)

def send_startup_message():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
    msg = (
        '🟢 <b>SISTEMA ELITE v2.0 - ONLINE</b>\n'
        + '<code>================================</code>\n'
        + 'Hora: ' + now + '\n'
        + 'Conexao Telegram:      OK\n'
        + 'Motor TradingView:     ATIVO\n'
        + 'Multi-Timeframe 1H+4H: ATIVO\n'
        + 'Cotacoes USD/EUR/USDC: ATIVAS\n'
        + 'Filtro ADX >= 20:      ATIVO\n'
        + '<code>================================</code>\n'
        + 'Scanner: 30 min | Noticias: 2h\n'
        + 'Comandos: /btc /news /status /ajuda\n'
        + '<code>================================</code>\n'
        + random.choice(SABEDORIA)
    )
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print('[ERRO] Startup: ' + str(e))

def scheduler_loop():
    schedule.every(30).minutes.do(send_trade_signal)
    schedule.every(2).hours.do(send_crypto_news)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    print('Iniciando Bot Elite v2.0…')
    bot.remove_webhook()
    time.sleep(2)
    send_startup_message()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print('[AVISO] ' + str(e))
            time.sleep(15)
