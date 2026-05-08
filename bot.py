“””
Bot Elite Pro v6.0 - Analise Tecnica Profissional (Webhook Mode)
Compativel com Railway. Sem caracteres Unicode problematicos em matplotlib.
“””

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
import socket
import hashlib
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify

# ═══════════════════════════════════════════════════════════

# CONFIGURACAO E VALIDACAO DE AMBIENTE

# ═══════════════════════════════════════════════════════════

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s [%(levelname)s] %(name)s: %(message)s’,
datefmt=’%Y-%m-%d %H:%M:%S’
)
logger = logging.getLogger(‘BotElitePro’)

TOKEN       = os.getenv(‘TELEGRAM_BOT_TOKEN’, ‘’).strip()
CHAT_ID     = os.getenv(‘TELEGRAM_CHAT_ID’, ‘-1003780528406’).strip()
WEBHOOK_URL = os.getenv(‘WEBHOOK_URL’, ‘’).strip()
PORT        = int(os.getenv(‘PORT’, 8000))

# Garante que WEBHOOK_URL sempre termina com /webhook

# Corrige o bug principal: Railway define a URL base sem o path,

# fazendo o Telegram postar em “/” (404).

if WEBHOOK_URL and not WEBHOOK_URL.rstrip(’/’).endswith(’/webhook’):
WEBHOOK_URL = WEBHOOK_URL.rstrip(’/’) + ‘/webhook’

def _validar_env():
erros = []
if not TOKEN:
erros.append(‘TELEGRAM_BOT_TOKEN nao configurado’)
if not WEBHOOK_URL:
erros.append(‘WEBHOOK_URL nao configurado (ex: https://seu-app.up.railway.app)’)
if erros:
for e in erros:
logger.critical(’[ERRO CRITICO] %s’, e)
raise SystemExit(1)

_validar_env()

bot = telebot.TeleBot(TOKEN, parse_mode=‘HTML’)
app = Flask(**name**)

SYMBOL_TV   = ‘BTCUSDT’
CCXT_SYMBOL = ‘BTC/USDT’

# ═══════════════════════════════════════════════════════════

# CACHE / CONTROLE DE SINAIS

# ═══════════════════════════════════════════════════════════

_ultimo_hash_sinal      = None
_tempo_ultimo_sinal     = 0.0
_ultimo_link_noticia    = None
_sinal_lock             = threading.Lock()
INTERVALO_MINIMO_SINAL  = 600   # segundos (10 min)

# ═══════════════════════════════════════════════════════════

# CONTEUDO EDUCACIONAL

# ═══════════════════════════════════════════════════════════

CONSELHOS = [
‘* Paciencia: O mercado premia quem aguarda a confluencia perfeita.’,
‘* Stop Loss: Nao e fraqueza - e marca do trader profissional.’,
‘* Psicologia: 80% do sucesso vem da mente, 20% da estrategia.’,
‘* Capital: Preserva-lo e a primeira e mais importante regra.’,
‘* Confluencia: 1H+4H sincronizados = probabilidade maxima de sucesso.’,
‘* Disciplina: Execute o plano mecanicamente, sem emocoes.’,
‘* Risco/Retorno: Nunca arrisque sem ao menos 1:2 de proporcao.’,
]

RECOMENDACOES = [
‘R:R minimo 1:2 | Capital por trade: maximo 2%’,
‘Stop Loss SEMPRE ativo - nenhuma excecao’,
‘Tome 50% no TP1 e deixe 50% correr ate TP2’,
‘Nunca dobre posicao - respeite o plano original’,
‘Gerencie emocoes ou saia do mercado por hoje’,
‘10% de lucro ja e sucesso - gananciosos fracassam’,
]

ALERTAS_RISCO = [
‘Confirmacao de entrada e OBRIGATORIA antes de executar’,
‘Sinal EDUCACIONAL - trade por sua conta e risco’,
‘Sempre respeite stops - mercado nao perdoa gananciosos’,
‘Volatilidade alta - reduza o tamanho da posicao’,
]

# ═══════════════════════════════════════════════════════════

# UTILITARIOS

# ═══════════════════════════════════════════════════════════

def *hash_sinal(direction: str, price: float, adx: float, rsi: float) -> str:
s = f’{direction}*{price:.2f}*{adx:.0f}*{rsi:.0f}’
return hashlib.md5(s.encode()).hexdigest()

def _agora_utc() -> str:
return datetime.now(timezone.utc).strftime(’%d/%m/%Y - %H:%M UTC’)

def _sep() -> str:
return ‘<code>===================================</code>’

# ═══════════════════════════════════════════════════════════

# DADOS DE MERCADO

# ═══════════════════════════════════════════════════════════

def get_multi_currency_prices(base: str = ‘BTC’) -> dict | None:
“””
Busca cotacoes individualmente para cada par.
Falhas parciais nao derrubam a funcao inteira.
“””
exchange = ccxt.binance()
pairs = {
‘USD’:  f’{base}/USDT’,
‘EUR’:  f’{base}/EUR’,
‘USDC’: f’{base}/USDC’,
}
prices: dict = {}
for currency, symbol in pairs.items():
try:
ticker = exchange.fetch_ticker(symbol)
prices[currency] = ticker[‘last’]
except Exception as exc:
logger.warning(‘Par %s indisponivel: %s’, symbol, exc)
prices[currency] = None

```
if prices.get('USD') is None:
    logger.error('Par %s/USDT indisponivel - abortando cotacao.', base)
    return None

prices['BRL'] = prices['USD'] * 5.15  # taxa estimada; substitua por API se precisar
return prices
```

def get_tradingview_analysis(symbol: str = SYMBOL_TV,
interval=Interval.INTERVAL_1_HOUR) -> dict | None:
try:
handler = TA_Handler(
symbol=symbol, screener=‘crypto’,
exchange=‘BINANCE’, interval=interval
)
a = handler.get_analysis()
bb_upper = a.indicators.get(‘BB.upper’, 0) or 0
bb_lower = a.indicators.get(‘BB.lower’, 0) or 0
return {
‘rec’:          a.summary[‘RECOMMENDATION’],
‘rsi’:          float(a.indicators.get(‘RSI’,    50) or 50),
‘adx’:          float(a.indicators.get(‘ADX’,    20) or 20),
‘atr’:          float(a.indicators.get(‘ATR’,     0) or 0),
‘buy_signals’:  int(a.summary.get(‘BUY’,  0)),
‘sell_signals’: int(a.summary.get(‘SELL’, 0)),
‘mfi’:          float(a.indicators.get(‘MFI’,    50) or 50),
‘stoch’:        float(a.indicators.get(‘Stoch.K’,50) or 50),
‘bb_width’:     float(bb_upper - bb_lower),
}
except Exception as exc:
logger.error(‘TradingView erro: %s’, exc)
return None

def get_confluence_signal() -> tuple:
“”“Retorna (direction | None, tv_data | None)”””
tf1h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_1_HOUR)
tf4h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_4_HOURS)
if not tf1h or not tf4h:
return None, tf1h

```
def _dir(rec: str) -> str:
    if 'BUY'  in rec: return 'BUY'
    if 'SELL' in rec: return 'SELL'
    return 'NEUTRO'

dir1h = _dir(tf1h['rec'])
dir4h = _dir(tf4h['rec'])
tf1h['tf4h_rec']   = tf4h['rec']
tf1h['confluence'] = (dir1h == dir4h and dir1h != 'NEUTRO')

if tf1h['confluence']:
    return dir1h, tf1h
return (dir1h if dir1h != 'NEUTRO' else None), tf1h
```

# ═══════════════════════════════════════════════════════════

# GRAFICO TECNICO

# ═══════════════════════════════════════════════════════════

def generate_premium_chart(symbol: str = CCXT_SYMBOL,
timeframe: str = ‘1h’,
limit: int = 120) -> str | None:
try:
exchange = ccxt.binance()
bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
df = pd.DataFrame(bars, columns=[‘time’, ‘open’, ‘high’, ‘low’, ‘close’, ‘volume’])
df[‘time’] = pd.to_datetime(df[‘time’], unit=‘ms’)
df.set_index(‘time’, inplace=True)

```
    # EMAs
    for span, col in [(9, 'EMA9'), (21, 'EMA21'), (50, 'EMA50'), (200, 'EMA200')]:
        df[col] = df['close'].ewm(span=span, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))

    # MACD
    df['EMA12']  = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA26']  = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD']   = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist']   = df['MACD'] - df['Signal']

    colors_macd = ['#00E5A0' if v >= 0 else '#FF3D6B' for v in df['Hist']]

    mc = mpf.make_marketcolors(
        up='#00E5A0', down='#FF3D6B',
        edge='inherit', wick='inherit', volume='in'
    )
    style = mpf.make_mpf_style(
        marketcolors=mc, gridstyle=':',
        y_on_right=True,
        facecolor='#0B0E1A', edgecolor='#1E2440', figcolor='#0B0E1A',
        rc={
            'text.color':        '#CDD6F4',
            'axes.labelcolor':   '#CDD6F4',
            'xtick.color':       '#CDD6F4',
            'ytick.color':       '#CDD6F4',
        }
    )

    n = len(df)
    # NOTA: linestyle usa '--' e ':' (ASCII) - nunca em-dash Unicode
    apds = [
        mpf.make_addplot(df['EMA9'],          color='#F5C842', width=1.2, panel=0),
        mpf.make_addplot(df['EMA21'],         color='#4DA6FF', width=1.2, panel=0),
        mpf.make_addplot(df['EMA50'],         color='#FF8C42', width=1.0, panel=0, linestyle='--'),
        mpf.make_addplot(df['EMA200'],        color='#9D4EDD', width=1.0, panel=0, linestyle=':'),
        mpf.make_addplot(df['RSI'],           color='#B06EFF', width=1.2, panel=2, ylabel='RSI'),
        mpf.make_addplot([70] * n,            color='#FF3D6B', width=0.8, panel=2, linestyle='--'),
        mpf.make_addplot([30] * n,            color='#00E5A0', width=0.8, panel=2, linestyle='--'),
        mpf.make_addplot(df['MACD'],          color='#4DA6FF', width=1.2, panel=3, ylabel='MACD'),
        mpf.make_addplot(df['Signal'],        color='#F5C842', width=1.2, panel=3),
        mpf.make_addplot(df['Hist'], type='bar', color=colors_macd, alpha=0.6, panel=3),
    ]

    # /tmp/ e o unico diretorio gravavel garantido no Railway
    fname = '/tmp/elite_chart_BTC.png'
    mpf.plot(
        df, type='candle', volume=True, style=style, addplot=apds,
        title='BITCOIN ELITE - ANALISE TECNICA PROFISSIONAL',
        savefig=fname, figsize=(16, 11),
        panel_ratios=(4, 1, 1.5, 1.5), tight_layout=True
    )
    return fname

except Exception as exc:
    logger.error('Grafico erro: %s', exc)
    return None
```

# ═══════════════════════════════════════════════════════════

# ENVIO DE SINAL DE TRADE

# ═══════════════════════════════════════════════════════════

def send_trade_signal(force: bool = False) -> None:
global _ultimo_hash_sinal, _tempo_ultimo_sinal

```
direction, tv_data = get_confluence_signal()
prices             = get_multi_currency_prices('BTC')

if not tv_data or not prices or not direction:
    logger.info('Sem sinal direcional no momento.')
    return

adx       = tv_data['adx']
rsi       = tv_data['rsi']
price_usd = prices['USD']
novo_hash = _hash_sinal(direction, price_usd, adx, rsi)

with _sinal_lock:
    agora = time.time()
    if not force:
        if novo_hash == _ultimo_hash_sinal:
            logger.info('Sinal identico ao anterior - bloqueado (anti-duplicata).')
            return
        delta = agora - _tempo_ultimo_sinal
        if delta < INTERVALO_MINIMO_SINAL:
            logger.info('Intervalo minimo nao atingido (%.0f min restantes).', (INTERVALO_MINIMO_SINAL - delta) / 60)
            return
        if adx < 20:
            logger.info('ADX baixo (%.1f) - tendencia fraca, sinal descartado.', adx)
            return
    _ultimo_hash_sinal  = novo_hash
    _tempo_ultimo_sinal = agora

# Gera grafico FORA do lock para nao bloquear outras threads
chart_file = generate_premium_chart()

is_buy      = (direction == 'BUY')
trade_label = 'COMPRA LONG' if is_buy else 'VENDA SHORT'
emoji_dir   = 'UP' if is_buy else 'DOWN'

price_eur   = prices.get('EUR')  or price_usd * 0.92
price_usdc  = prices.get('USDC') or price_usd
price_brl   = prices.get('BRL')  or price_usd * 5.15

atr       = tv_data['atr'] or (price_usd * 0.015)
conf      = tv_data.get('confluence', False)
tf4h_rec  = tv_data.get('tf4h_rec', 'N/D')
buy_sig   = tv_data.get('buy_signals', 0)
sell_sig  = tv_data.get('sell_signals', 0)
mfi       = tv_data.get('mfi', 50)
stoch     = tv_data.get('stoch', 50)

mult_sl, mult_tp1, mult_tp2 = 1.5, 1.5, 3.0
if is_buy:
    sl   = price_usd - atr * mult_sl
    tp1  = price_usd + atr * mult_tp1
    tp2  = price_usd + atr * mult_tp2
else:
    sl   = price_usd + atr * mult_sl
    tp1  = price_usd - atr * mult_tp1
    tp2  = price_usd - atr * mult_tp2

risco = abs(sl - price_usd) or 1
rr1   = abs(tp1 - price_usd) / risco
rr2   = abs(tp2 - price_usd) / risco

# Classificadores de indicadores
def _adx_lbl(v):
    return 'Forte' if v > 25 else 'Moderado' if v > 20 else 'Fraco'

def _rsi_lbl(v):
    return 'Sobrecomprado' if v > 70 else 'Sobrevendido' if v < 30 else 'Neutro'

def _osc_lbl(v):
    return 'Alto' if v > 80 else 'Baixo' if v < 20 else 'Moderado'

conf_badge = 'CONFLUENCIA 1H+4H' if conf else 'Sinal 1H'

msg = (
    f'<b>OPORTUNIDADE IDENTIFICADA [{emoji_dir}]</b>\n'
    f'{_sep()}\n'
    f'Horario: <i>{_agora_utc()}</i>\n'
    f'Ativo: Bitcoin (BTC/USDT) | Timeframe: 1H\n'
    f'<b>Operacao: <code>{trade_label}</code></b>\n'
    f'Status: {conf_badge}\n'
    f'{_sep()}\n'
    f'<b>INDICADORES TECNICOS:</b>\n'
    f'  ADX: {_adx_lbl(adx)} ({adx:.1f}) - forca da tendencia\n'
    f'  RSI: {_rsi_lbl(rsi)} ({rsi:.1f})\n'
    f'  MFI: {_osc_lbl(mfi)} ({mfi:.1f}) - fluxo de dinheiro\n'
    f'  Stochastic: {_osc_lbl(stoch)} ({stoch:.1f})\n'
    f'  Sinais 1H: {buy_sig} compra / {sell_sig} venda\n'
    f'  4H Recomendacao: <code>{tf4h_rec}</code>\n'
    f'{_sep()}\n'
    f'<b>PRECOS DE ENTRADA (SPOT):</b>\n'
    f'  USD:  <code>${price_usd:,.2f}</code>\n'
    f'  EUR:  <code>E{price_eur:,.2f}</code>\n'
    f'  USDC: <code>{price_usdc:,.2f}</code>\n'
    f'  BRL:  <code>R${price_brl:,.2f}</code>\n'
    f'{_sep()}\n'
    f'<b>NIVEIS DE REALIZACAO:</b>\n'
    f'  TP1 (R:R {rr1:.1f}:1) - ${tp1:,.2f}\n'
    f'  TP2 (R:R {rr2:.1f}:1) - ${tp2:,.2f}\n'
    f'<b>STOP LOSS (PROTECAO):</b>\n'
    f'  <code>${sl:,.2f}</code>\n'
    f'{_sep()}\n'
    f'Volatilidade (ATR): ${atr:,.2f}\n'
    f'Tipo de sinal: {"Confluencia Forte" if conf else "Tendencia 1H"}\n'
    f'Risco recomendado: Max 2% do capital total\n'
    f'{_sep()}\n'
    f'<b>RECOMENDACAO:</b> {random.choice(RECOMENDACOES)}\n'
    f'{_sep()}\n'
    f'<b>AVISO:</b> {random.choice(ALERTAS_RISCO)}\n'
    f'{_sep()}\n'
    f'<i>{random.choice(CONSELHOS)}</i>\n'
    f'{_sep()}\n'
    f'<i>Sinal gerado automaticamente. Use com responsabilidade.</i>'
)

try:
    if chart_file and os.path.exists(chart_file):
        with open(chart_file, 'rb') as photo:
            bot.send_photo(CHAT_ID, photo, caption=msg)
        logger.info('Sinal enviado COM grafico: %s', trade_label)
    else:
        bot.send_message(CHAT_ID, msg)
        logger.info('Sinal enviado SEM grafico: %s', trade_label)
except Exception as exc:
    logger.error('Erro ao enviar sinal: %s', exc)
    # Reverte cache para permitir nova tentativa
    with _sinal_lock:
        _ultimo_hash_sinal  = None
        _tempo_ultimo_sinal = 0.0
finally:
    if chart_file and os.path.exists(chart_file):
        try:
            os.remove(chart_file)
        except OSError:
            pass
```

# ═══════════════════════════════════════════════════════════

# NOTICIAS

# ═══════════════════════════════════════════════════════════

def send_crypto_news() -> None:
global _ultimo_link_noticia
old_timeout = socket.getdefaulttimeout()
try:
socket.setdefaulttimeout(15)
feed = feedparser.parse(‘https://cointelegraph.com.br/rss’)
finally:
socket.setdefaulttimeout(old_timeout)

```
try:
    for entry in feed.entries[:5]:
        link = getattr(entry, 'link', None)
        if not link or link == _ultimo_link_noticia:
            continue
        _ultimo_link_noticia = link
        title   = getattr(entry, 'title', 'Sem titulo')
        summary = getattr(entry, 'summary', '')[:300]
        msg = (
            f'<b>NOTICIAS DO MERCADO CRIPTO</b>\n'
            f'{_sep()}\n'
            f'<b>{title}</b>\n\n'
            f'<i>{summary}...</i>\n\n'
            f'<a href="{link}">Ler materia completa</a>\n'
            f'{_sep()}\n'
            f'<i>{random.choice(CONSELHOS)}</i>'
        )
        bot.send_message(CHAT_ID, msg, disable_web_page_preview=False)
        logger.info('Noticia enviada: %s', title)
        break
except Exception as exc:
    logger.error('Noticias erro: %s', exc)
```

# ═══════════════════════════════════════════════════════════

# COMANDOS DO BOT

# ═══════════════════════════════════════════════════════════

@bot.message_handler(commands=[‘start’, ‘ajuda’])
def cmd_start(msg):
texto = (
‘<b>BOT ELITE PRO v6.0 - ANALISE TECNICA PROFISSIONAL</b>\n\n’
‘<b>COMANDOS DISPONIVEIS:</b>\n’
f’{_sep()}\n’
‘/analise - Analise tecnica profissional INSTANTANEA\n’
‘/noticias - Ultimas noticias relevantes do mercado cripto\n’
‘/status   - Status do sistema e cotacoes em tempo real\n’
‘/ajuda    - Exibe este menu\n’
f’{_sep()}\n’
‘<b>CARACTERISTICAS:</b>\n’
’  Analises automaticas a cada 30 minutos\n’
’  Sinais instantaneos com anti-duplicata\n’
’  Multi-timeframe: 1H + 4H com confluencia\n’
’  7 indicadores: ADX, RSI, MACD, ATR, MFI, Stoch, EMA\n’
’  Graficos tecnicos com 4 paineis\n’
’  Cotacoes em USD, EUR, USDC e BRL\n’
’  TP e SL calculados automaticamente via ATR\n’
f’{_sep()}\n’
‘AVISO: Sinais sao educacionais. Trade por sua conta e risco!’
)
bot.send_message(msg.chat.id, texto)

@bot.message_handler(commands=[‘analise’])
def cmd_analise(msg):
bot.send_message(msg.chat.id, ‘<b>Analisando mercado… aguarde.</b>’)
threading.Thread(target=send_trade_signal, kwargs={‘force’: True}, daemon=True).start()

@bot.message_handler(commands=[‘noticias’])
def cmd_noticias(msg):
bot.send_message(msg.chat.id, ‘<b>Buscando ultimas noticias…</b>’)
threading.Thread(target=send_crypto_news, daemon=True).start()

@bot.message_handler(commands=[‘status’])
def cmd_status(msg):
prices = get_multi_currency_prices(‘BTC’)
tv     = get_tradingview_analysis()
if prices and tv:
price_eur  = prices.get(‘EUR’)  or 0.0
price_usdc = prices.get(‘USDC’) or 0.0
price_brl  = prices.get(‘BRL’)  or 0.0
texto = (
‘<b>SISTEMA ONLINE - TODAS AS FUNCOES ATIVAS</b>\n’
f’{_sep()}\n’
f’Horario: {_agora_utc()}\n’
f’{_sep()}\n’
‘<b>COTACAO BITCOIN (SPOT):</b>\n’
f’  USD:  <code>${prices[“USD”]:,.2f}</code>\n’
f’  EUR:  <code>E{price_eur:,.2f}</code>\n’
f’  USDC: <code>{price_usdc:,.2f}</code>\n’
f’  BRL:  <code>R${price_brl:,.2f}</code>\n’
f’{_sep()}\n’
‘<b>INDICADORES TECNICOS (1H):</b>\n’
f’  RSI: <code>{tv[“rsi”]:.1f}</code>\n’
f’  ADX: <code>{tv[“adx”]:.1f}</code>\n’
f’  MFI: <code>{tv[“mfi”]:.1f}</code>\n’
f’  ATR: <code>${tv[“atr”]:.2f}</code>\n’
f’  Recomendacao: <code>{tv[“rec”]}</code>\n’
f’{_sep()}\n’
‘<b>STATUS DOS COMPONENTES:</b>\n’
’  Telegram API: Conectada\n’
’  Binance API:  Conectada\n’
’  TradingView:  Conectada\n’
’  Scheduler:    Ativo\n’
’  Anti-Dup:     Ativo\n’
f’{_sep()}’
)
else:
texto = ‘<b>Erro ao conectar.</b> Tente novamente em alguns instantes.’
bot.send_message(msg.chat.id, texto)

# ═══════════════════════════════════════════════════════════

# MENSAGEM DE INICIALIZACAO

# ═══════════════════════════════════════════════════════════

def send_startup_message() -> None:
msg = (
‘<b>SISTEMA ELITE PRO v6.0 - INICIALIZADO (WEBHOOK MODE)</b>\n’
f’{_sep()}\n’
f’Horario: {_agora_utc()}\n’
f’{_sep()}\n’
‘<b>MODULOS ATIVADOS:</b>\n’
’  Telegram Webhook (SSL)\n’
’  Binance API (tempo real)\n’
’  TradingView - Analise Tecnica\n’
’  Multi-Timeframe 1H + 4H\n’
’  Grafico com 4 paineis (EMA, Vol, RSI, MACD)\n’
’  Feed de Noticias RSS\n’
’  Protecao Anti-Duplicata\n’
f’{_sep()}\n’
‘<b>CONFIGURACAO:</b>\n’
’  Analises:   a cada 30 minutos\n’
’  Noticias:   a cada 2 horas\n’
’  Min. sinal: 10 minutos\n’
f’{_sep()}\n’
‘Comandos: /analise /noticias /status /ajuda\n’
f’{_sep()}\n’
f’<i>{random.choice(CONSELHOS)}</i>\n’
f’{_sep()}\n’
‘<b>Sistema pronto para operacoes!</b>’
)
try:
bot.send_message(CHAT_ID, msg)
logger.info(‘Mensagem de startup enviada.’)
except Exception as exc:
logger.error(‘Startup msg erro: %s’, exc)

# ═══════════════════════════════════════════════════════════

# FLASK ROUTES (WEBHOOK)

# ═══════════════════════════════════════════════════════════

@app.route(’/webhook’, methods=[‘POST’])
def webhook_handler():
“””
Recebe updates do Telegram via webhook.
O WEBHOOK_URL deve apontar para esta rota (ex: https://app.railway.app/webhook).
Este modulo corrige automaticamente a URL se ela nao incluir /webhook.
“””
try:
json_data = request.get_json(force=True, silent=True)
if not json_data:
logger.warning(‘Webhook recebeu payload vazio ou invalido.’)
return jsonify({‘status’: ‘ignored’}), 200
update = telebot.types.Update.de_json(json_data)
bot.process_new_updates([update])
logger.info(‘Update %s processado.’, getattr(update, ‘update_id’, ‘?’))
return jsonify({‘status’: ‘ok’}), 200
except Exception as exc:
logger.error(‘Webhook erro: %s’, exc)
return jsonify({‘status’: ‘error’, ‘detail’: str(exc)}), 400

@app.route(’/’, methods=[‘GET’, ‘POST’])
def root():
“””
Rota raiz: evita 404 caso algo envie para ‘/’ por engano.
GET -> health check simples.
POST -> redireciona logicamente para o handler de webhook.
“””
if request.method == ‘POST’:
logger.warning(‘POST recebido em / - redirecionando para /webhook’)
return webhook_handler()
return jsonify({‘status’: ‘ok’, ‘service’: ‘Bot Elite Pro v6.0’}), 200

@app.route(’/health’, methods=[‘GET’])
def health():
“”“Health check para Railway / uptime monitors.”””
return jsonify({
‘status’: ‘ok’,
‘time’:   _agora_utc(),
‘webhook’: WEBHOOK_URL,
}), 200

# ═══════════════════════════════════════════════════════════

# SCHEDULER

# ═══════════════════════════════════════════════════════════

def _scheduler_loop() -> None:
schedule.every(30).minutes.do(send_trade_signal)
schedule.every(2).hours.do(send_crypto_news)
logger.info(‘Scheduler iniciado: sinais cada 30min, noticias cada 2h.’)
while True:
try:
schedule.run_pending()
time.sleep(1)
except Exception as exc:
logger.error(‘Scheduler erro: %s’, exc)
time.sleep(5)

# ═══════════════════════════════════════════════════════════

# ENTRYPOINT

# ═══════════════════════════════════════════════════════════

if **name** == ‘**main**’:
logger.info(‘Iniciando Bot Elite Pro v6.0 (WEBHOOK MODE)…’)

```
# Remove webhook anterior
try:
    bot.remove_webhook()
    time.sleep(1)
    logger.info('Webhook anterior removido.')
except Exception as exc:
    logger.warning('Nao foi possivel remover webhook anterior: %s', exc)

# Configura novo webhook
try:
    bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info('Webhook configurado: %s', WEBHOOK_URL)
except Exception as exc:
    logger.critical('Falha ao configurar webhook: %s', exc)
    raise SystemExit(1)

# Startup
send_startup_message()

# Scheduler em thread daemon
threading.Thread(target=_scheduler_loop, daemon=True).start()

# Flask
logger.info('Flask iniciando na porta %d...', PORT)
app.run(host='0.0.0.0', port=PORT, debug=False)
```
