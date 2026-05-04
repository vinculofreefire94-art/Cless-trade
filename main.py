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
import hashlib

TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '-1003780528406')

if not TOKEN:
    print('[ERRO CRÍTICO] TELEGRAM_BOT_TOKEN não configurado!')
    print('Configure a variável de ambiente TELEGRAM_BOT_TOKEN no Railway')
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
bot.remove_webhook()
time.sleep(0.5)

SYMBOL_TV   = 'BTCUSDT'
CCXT_SYMBOL = 'BTC/USDT'

# ═══════════════════════════════════════════════════════════
# CACHE INTELIGENTE DE SINAIS
# ═══════════════════════════════════════════════════════════
ultimo_sinal_enviado    = None
ultimo_hash_sinal       = None
tempo_ultimo_sinal      = 0
INTERVALO_MINIMO_SINAL  = 600  # 10 minutos entre sinais
ultimo_link_noticia     = None
sinal_lock              = threading.Lock()

# ═══════════════════════════════════════════════════════════
# CONSELHOS E RECOMENDAÇÕES PROFISSIONAIS
# ═══════════════════════════════════════════════════════════

CONSELHOS = [
    '💡 <i><b>Paciência Profissional:</b> O mercado premia os que aguardam a confluência PERFEITA.</i>',
    '🎯 <i><b>Stop Loss:</b> Não é fraqueza - é a marca do TRADER PROFISSIONAL.</i>',
    '⚖️ <i><b>Psicologia:</b> 80% do sucesso vem da mente, 20% da estratégia.</i>',
    '💎 <i><b>Capital:</b> Preservá-lo é A PRIMEIRA E MAIS IMPORTANTE REGRA.</i>',
    '📊 <i><b>Confluência:</b> 1H+4H sincronizados = Probabilidade MÁXIMA de sucesso.</i>',
    '🔥 <i><b>Disciplina:</b> Execute o plano mecanicamente, sem emoções.</i>',
    '💰 <i><b>Risco/Retorno:</b> Nunca arrisque sem ao menos 1:2 de proporção.</i>',
]

RECOMENDACOES = [
    '✅ <b>Regra de Ouro:</b> R:R mínimo 1:2 | Capital por trade: máximo 2%',
    '✅ <b>Stop Loss:</b> SEMPRE ativo - nenhuma exceção, nenhum descuido',
    '✅ <b>Take Profit:</b> Tome 50% em TP1 e deixe 50% correr em TP2',
    '✅ <b>Posição:</b> Nunca dobre posição - respeite o plano original',
    '✅ <b>Emocional:</b> Gerencie emoções ou saia do mercado por hoje',
    '✅ <b>Trades Ruins:</b> Culpe-se, aprenda e siga em frente',
    '✅ <b>Gestão:</b> 10% lucro é sucesso - gananciosos fracassam',
]

ALERTAS_RISCO = [
    '⚠️ <i>Atenção: Confirmação de entrada é OBRIGATÓRIA antes de executar</i>',
    '⚠️ <i>Este sinal é EDUCACIONAL - Trade por sua conta e risco</i>',
    '⚠️ <i>Sempre respeite STOPS - mercado não perdoa ganância</i>',
    '⚠️ <i>Volatilidade alta - aumente cautela e reduza tamanho da posição</i>',
]

def gerar_hash_sinal(direction, price_usd, adx, rsi):
    """Gera hash único para identificar sinais idênticos"""
    sinal_str = f"{direction}_{price_usd:.2f}_{adx:.0f}_{rsi:.0f}"
    return hashlib.md5(sinal_str.encode()).hexdigest()

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
            'BRL':  tickers[base_asset + '/USDT']['last'] * 5.15 if base_asset == 'BTC' else 0,
        }
    except Exception as e:
        print(f'[ERRO] Cotações: {str(e)}')
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
            'mfi':          a.indicators.get('MFI', 50),
            'stoch':        a.indicators.get('Stoch.K', 50),
            'bb_width':     a.indicators.get('BB.upper', 0) - a.indicators.get('BB.lower', 0),
        }
    except Exception as e:
        print(f'[ERRO] TradingView: {str(e)}')
        return None

def get_confluence_signal():
    tf1h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_1_HOUR)
    tf4h = get_tradingview_analysis(SYMBOL_TV, Interval.INTERVAL_4_HOURS)
    if not tf1h or not tf4h:
        return None, tf1h
    
    def direction(rec):
        if 'BUY'  in rec: return 'BUY'
        if 'SELL' in rec: return 'SELL'
        return 'NEUTRO'
    
    dir1h = direction(tf1h['rec'])
    dir4h = direction(tf4h['rec'])
    tf1h['tf4h_rec'] = tf4h['rec']
    
    if dir1h == dir4h and dir1h != 'NEUTRO':
        tf1h['confluence'] = True
        return dir1h, tf1h
    
    tf1h['confluence'] = False
    return (dir1h if dir1h != 'NEUTRO' else None), tf1h

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
        df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
        
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
        
        mc = mpf.make_marketcolors(up='#00E5A0', down='#FF3D6B', edge='inherit', wick='inherit', volume='in')
        s  = mpf.make_mpf_style(
            marketcolors=mc, gridstyle=':', y_on_right=True,
            facecolor='#0B0E1A', edgecolor='#1E2440', figcolor='#0B0E1A',
            rc={'text.color': '#CDD6F4', 'axes.labelcolor': '#CDD6F4', 'xtick.color': '#CDD6F4', 'ytick.color': '#CDD6F4'}
        )
        
        apds = [
            mpf.make_addplot(df['EMA9'],    color='#F5C842', width=1.2, panel=0),
            mpf.make_addplot(df['EMA21'],   color='#4DA6FF', width=1.2, panel=0),
            mpf.make_addplot(df['EMA50'],   color='#FF8C42', width=1.0, panel=0, linestyle='–'),
            mpf.make_addplot(df['EMA200'],  color='#9D4EDD', width=1.0, panel=0, linestyle=':'),
            mpf.make_addplot(df['RSI'],     panel=2, color='#B06EFF', ylabel='RSI',  width=1.2),
            mpf.make_addplot([70]*len(df), panel=2, color='#FF3D6B', linestyle='–', width=0.8),
            mpf.make_addplot([30]*len(df), panel=2, color='#00E5A0', linestyle='–', width=0.8),
            mpf.make_addplot(df['MACD'],   panel=3, color='#4DA6FF', ylabel='MACD', width=1.2),
            mpf.make_addplot(df['Signal'], panel=3, color='#F5C842', width=1.2),
            mpf.make_addplot(df['Hist'],   type='bar', panel=3, color=colors_macd, alpha=0.6),
        ]
        
        fname = 'elite_chart_BTC.png'
        mpf.plot(df, type='candle', volume=True, style=s, addplot=apds,
                title='📊 BITCOIN ELITE - ANÁLISE TÉCNICA PROFISSIONAL',
                savefig=fname, figsize=(16, 11), panel_ratios=(4, 1, 1.5, 1.5), tight_layout=True)
        return fname
    except Exception as e:
        print(f'[ERRO] Gráfico: {str(e)}')
        return None

def send_trade_signal(force=False):
    global ultimo_sinal_enviado, ultimo_hash_sinal, tempo_ultimo_sinal
    
    with sinal_lock:
        tempo_agora = time.time()
        
        direction, tv_data = get_confluence_signal()
        prices = get_multi_currency_prices('BTC')
        
        if not tv_data or not prices or not direction:
            print('[INFO] Sem sinal direcional no momento.')
            return
        
        is_buy     = direction == 'BUY'
        trade_type = 'COMPRA LONG 🟢' if is_buy else 'VENDA SHORT 🔴'
        
        adx = tv_data['adx']
        rsi = tv_data['rsi']
        
        # Gerar hash do sinal
        novo_hash = gerar_hash_sinal(direction, prices['USD'], adx, rsi)
        
        # Verificar se é sinal duplicado
        if novo_hash == ultimo_hash_sinal and not force:
            print('[INFO] Sinal identico ao anterior - BLOQUEADO para evitar duplicata.')
            return
        
        # Verificar intervalo mínimo entre sinais (10 minutos)
        if not force and (tempo_agora - tempo_ultimo_sinal) < INTERVALO_MINIMO_SINAL:
            minutos_restantes = (INTERVALO_MINIMO_SINAL - (tempo_agora - tempo_ultimo_sinal)) / 60
            print(f'[INFO] Intervalo mínimo não atingido. Aguarde {minutos_restantes:.0f} minutos.')
            return
        
        # Filtro ADX
        if adx < 20 and not force:
            print(f'[INFO] ADX baixo ({adx:.1f}) - tendência fraca. Descartado.')
            return
        
        # Atualizar cache
        ultimo_sinal_enviado = trade_type
        ultimo_hash_sinal = novo_hash
        tempo_ultimo_sinal = tempo_agora
        
        price_usd  = prices['USD']
        price_eur  = prices['EUR']
        price_usdc = prices['USDC']
        price_brl  = prices['BRL']
        atr        = tv_data['atr'] if tv_data['atr'] else (price_usd * 0.015)
        confluence = tv_data.get('confluence', False)
        tf4h_rec   = tv_data.get('tf4h_rec', 'N/D')
        buy_sig    = tv_data.get('buy_signals', 0)
        sell_sig   = tv_data.get('sell_signals', 0)
        mfi        = tv_data.get('mfi', 50)
        stoch      = tv_data.get('stoch', 50)
        
        chart_emoji = '📈' if is_buy else '📉'
        conf_badge  = '✅ CONFLUÊNCIA 1H+4H' if confluence else '⚠️ Sinal 1H'
        
        mult_sl, mult_tp1, mult_tp2 = 1.5, 1.5, 3.0
        
        if is_buy:
            sl_usd  = price_usd - (atr * mult_sl)
            tp1_usd = price_usd + (atr * mult_tp1)
            tp2_usd = price_usd + (atr * mult_tp2)
        else:
            sl_usd  = price_usd + (atr * mult_sl)
            tp1_usd = price_usd - (atr * mult_tp1)
            tp2_usd = price_usd - (atr * mult_tp2)
        
        rr_tp1 = abs(tp1_usd - price_usd) / abs(sl_usd - price_usd) if abs(sl_usd - price_usd) > 0 else 0
        rr_tp2 = abs(tp2_usd - price_usd) / abs(sl_usd - price_usd) if abs(sl_usd - price_usd) > 0 else 0
        
        adx_text = '🔥 Forte' if adx > 25 else '⚡ Moderado' if adx > 20 else '⚠️ Fraco'
        rsi_text = '🔴 Sobrecomprado' if rsi > 70 else '🟢 Sobrevendido' if rsi < 30 else '🟡 Neutro'
        mfi_text = '🔴 Alto' if mfi > 80 else '🟢 Baixo' if mfi < 20 else '🟡 Moderado'
        stoch_text = '🔴 Alto' if stoch > 80 else '🟢 Baixo' if stoch < 20 else '🟡 Normal'
        now_str  = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
        
        # Gerar gráfico ANTES de enviar mensagem
        chart_file = generate_premium_chart()
        
        msg = (
            f'{chart_emoji} <b>⚡ OPORTUNIDADE IDENTIFICADA</b> {chart_emoji}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + f'⏰ <b>Horário:</b> <i>{now_str}</i>\n'
            + f'📍 <b>Ativo:</b> Bitcoin (BTC/USDT) • Timeframe: 1H\n'
            + f'<b>🎯 Operação:</b> <code>{trade_type}</code>\n'
            + f'<b>📊 Status:</b> {conf_badge}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + f'<b>📈 INDICADORES TÉCNICOS:</b>\n'
            + f'  • ADX: {adx_text} ({adx:.1f}) - FORÇA DA TENDÊNCIA\n'
            + f'  • RSI: {rsi_text} ({rsi:.1f})\n'
            + f'  • MFI: {mfi_text} ({mfi:.1f}) - FLUXO DE DINHEIRO\n'
            + f'  • Stochastic: {stoch_text} ({stoch:.1f})\n'
            + f'  • Sinais 1H: {buy_sig}📈 / {sell_sig}📉\n'
            + f'  • 4H Recomendação: <code>{tf4h_rec}</code>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>💰 PREÇOS DE ENTRADA (SPOT):</b>\n'
            + f'  USD:  <code>${price_usd:,.2f}</code>\n'
            + f'  EUR:  <code>€{price_eur:,.2f}</code>\n'
            + f'  USDC: <code>{price_usdc:,.2f}</code>\n'
            + f'  BRL:  <code>R${price_brl:,.2f}</code>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>🎯 NÍVEIS DE REALIZAÇÃO:</b>\n'
            + f'  TP1 (R:R {rr_tp1:.1f}:1) 🎖️  ${tp1_usd:,.2f}\n'
            + f'  TP2 (R:R {rr_tp2:.1f}:1) 👑  ${tp2_usd:,.2f}\n'
            + '<b>🛑 STOP LOSS (PROTEÇÃO):</b>\n'
            + f'  <code>${sl_usd:,.2f}</code>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + f'<b>📊 VOLATILIDADE (ATR):</b> ${atr:,.2f}\n'
            + f'<b>💡 Tipo de Sinal:</b> {"Confluência Forte ⭐" if confluence else "Tendência 1H"}\n'
            + f'<b>⚠️ Risco Recomendado:</b> Máx 2% do capital total\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>📋 RECOMENDAÇÃO EXECUTIVA:</b>\n'
            + f'  {random.choice(RECOMENDACOES)}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>🚨 AVISO DE RISCO:</b>\n'
            + f'  {random.choice(ALERTAS_RISCO)}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + f'{random.choice(CONSELHOS)}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '📲 <i>Sinal gerado automaticamente • Use com responsabilidade</i>'
        )
        
        try:
            if chart_file and os.path.exists(chart_file):
                with open(chart_file, 'rb') as photo:
                    bot.send_photo(CHAT_ID, photo, caption=msg)
                print(f'✅ SINAL ENVIADO COM GRÁFICO: {trade_type}')
            else:
                bot.send_message(CHAT_ID, msg)
                print(f'✅ SINAL ENVIADO (sem gráfico): {trade_type}')
        except Exception as e:
            print(f'[ERRO] Envio: {str(e)}')
            # Resetar cache em caso de erro
            ultimo_hash_sinal = None
            tempo_ultimo_sinal = 0
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
                summary = getattr(entry, 'summary', '')[:300]
                msg = (
                    '🌍 <b>NOTÍCIAS DO MERCADO CRIPTO</b>\n'
                    + '<code>═══════════════════════════════════</code>\n'
                    + f'<b>📰 {entry.title}</b>\n\n'
                    + f'<i>{summary}…</i>\n\n'
                    + f'<a href="{entry.link}">🔗 Ler matéria completa</a>\n'
                    + '<code>═══════════════════════════════════</code>\n'
                    + f'{random.choice(CONSELHOS)}'
                )
                bot.send_message(CHAT_ID, msg, disable_web_page_preview=False)
                print('✅ NOTÍCIA ENVIADA')
                break
    except Exception as e:
        print(f'[ERRO] Notícias: {str(e)}')

@bot.message_handler(commands=['start', 'ajuda'])
def cmd_start(msg):
    help_text = (
        '<b>🤖 BOT ELITE PRO - ANÁLISE TÉCNICA DE TRADING PROFISSIONAL</b>\n\n'
        '<b>📋 COMANDOS DISPONÍVEIS:</b>\n'
        '<code>═══════════════════════════════════</code>\n'
        '<b>/análise</b> - Análise técnica profissional INSTANTÂNEA\n'
        '<b>/notícias</b> - Últimas notícias relevantes do mercado cripto\n'
        '<b>/status</b> - Status do sistema e cotações em tempo real\n'
        '<b>/ajuda</b> - Exibe este menu\n'
        '<code>═══════════════════════════════════</code>\n'
        '<b>ℹ️ CARACTERÍSTICAS AVANÇADAS:</b>\n'
        '✅ Análises automáticas a cada 30 minutos\n'
        '✅ Sinais INSTANTÂNEOS quando oportunidade é detectada\n'
        '✅ Multi-timeframe (1H + 4H) com confluência\n'
        '✅ 7 Indicadores profissionais: ADX, RSI, MACD, ATR, MFI, Stochastic, EMA\n'
        '✅ Gráficos técnicos avançados com 4 painéis\n'
        '✅ Cotações em 4 moedas: USD, EUR, USDC, BRL\n'
        '✅ Cálculos automáticos de TP e SL com ATR\n'
        '✅ Taxa R:R otimizada (até 3:1 em TP2)\n'
        '✅ PROTEÇÃO contra mensagens duplicadas\n'
        '<code>═══════════════════════════════════</code>\n'
        '⚠️ IMPORTANTE: Sinais são educacionais. Trade por sua conta e risco!\n'
    )
    bot.send_message(msg.chat.id, help_text)

@bot.message_handler(commands=['análise', 'analise'])
def cmd_btc(msg):
    bot.send_message(msg.chat.id, '⏳ <b>Analisando mercado profundamente...</b>\n⏱️ Aguarde…')
    threading.Thread(target=send_trade_signal, kwargs={'force': True}, daemon=True).start()

@bot.message_handler(commands=['notícias', 'noticias'])
def cmd_news(msg):
    bot.send_message(msg.chat.id, '🔍 <b>Buscando últimas notícias...</b>')
    threading.Thread(target=send_crypto_news, daemon=True).start()

@bot.message_handler(commands=['status'])
def cmd_status(msg):
    prices = get_multi_currency_prices('BTC')
    tv     = get_tradingview_analysis()
    now    = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
    if prices and tv:
        status = (
            '✅ <b>SISTEMA ONLINE - TODAS AS FUNÇÕES ATIVAS</b>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + f'⏰ {now}\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>💰 COTAÇÃO BITCOIN (SPOT):</b>\n'
            + f'  USD:  <code>${prices["USD"]:,.2f}</code>\n'
            + f'  EUR:  <code>€{prices["EUR"]:,.2f}</code>\n'
            + f'  USDC: <code>{prices["USDC"]:,.2f}</code>\n'
            + f'  BRL:  <code>R${prices["BRL"]:,.2f}</code>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '<b>📊 INDICADORES TÉCNICOS (1H):</b>\n'
            + f'  RSI:    <code>{tv["rsi"]:.1f}</code>\n'
            + f'  ADX:    <code>{tv["adx"]:.1f}</code>\n'
            + f'  MFI:    <code>{tv["mfi"]:.1f}</code>\n'
            + f'  ATR:    <code>${tv["atr"]:.2f}</code>\n'
            + f'  Recomendação: <code>{tv["rec"]}</code>\n'
            + '<code>═══════════════════════════════════</code>\n'
            + '🟢 <b>Status dos Componentes:</b>\n'
            + '  ✅ API Telegram: Conectada\n'
            + '  ✅ API Binance: Conectada\n'
            + '  ✅ TradingView: Conectada\n'
            + '  ✅ Análise Automática: ATIVA\n'
            + '  ✅ Detecção de Sinais: ATIVA\n'
            + '  ✅ Proteção Anti-Duplicata: ATIVA\n'
            + '<code>═══════════════════════════════════</code>'
        )
    else:
        status = '❌ <b>Erro ao conectar.</b> Tente novamente em alguns instantes.'
    bot.send_message(msg.chat.id, status)

def send_startup_message():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y - %H:%M UTC')
    msg = (
        '🟢 <b>SISTEMA ELITE PRO v5.0 - INICIALIZADO</b>\n'
        + '<code>═══════════════════════════════════</code>\n'
        + f'⏰ {now}\n'
        + '<code>═══════════════════════════════════</code>\n'
        + '<b>🔧 MÓDULOS ATIVADOS:</b>\n'
        + '  ✅ Conexão Telegram (SSL seguro)\n'
        + '  ✅ API Binance (Cotações em tempo real)\n'
        + '  ✅ Motor TradingView (Análise Técnica)\n'
        + '  ✅ Análise Multi-Timeframe 1H+4H\n'
        + '  ✅ Detecção de Confluência\n'
        + '  ✅ Cálculo de ATR e Volatilidade\n'
        + '  ✅ 7 Indicadores Técnicos\n'
        + '  ✅ Gerador de Gráficos Profissionais\n'
        + '  ✅ Feed de Notícias RSS\n'
        + '  ✅ PROTEÇÃO Anti-Duplicata INTELIGENTE\n'
        + '<code>═══════════════════════════════════</code>\n'
        + '<b>📊 CONFIGURAÇÃO OTIMIZADA:</b>\n'
        + '  • Análises: a cada 30 minutos\n'
        + '  • Notícias: a cada 2 horas\n'
        + '  • Sinais: INSTANTÂNEOS (sem duplicatas)\n'
        + '  • Intervalo mínimo entre sinais: 10 minutos\n'
        + '  • Multi-timeframe: 1H + 4H com confluência\n'
        + '  • Cotações em: USD, EUR, USDC, BRL\n'
        + '<code>═══════════════════════════════════</code>\n'
        + '<b>📱 COMANDOS DISPONÍVEIS:</b>\n'
        + '  /análise /notícias /status /ajuda\n'
        + '<code>═══════════════════════════════════</code>\n'
        + f'{random.choice(CONSELHOS)}\n'
        + '<code>═══════════════════════════════════</code>\n'
        + '🚀 Sistema pronto para operações!'
    )
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print(f'[ERRO] Startup: {str(e)}')

def scheduler_loop():
    schedule.every(30).minutes.do(send_trade_signal)
    schedule.every(2).hours.do(send_crypto_news)
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f'[ERRO] Scheduler: {str(e)}')
            time.sleep(5)

if __name__ == '__main__':
    print('🚀 Iniciando Bot Elite Pro v5.0...')
    send_startup_message()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    
    while True:
        try:
            print('📡 Ativando polling de mensagens...')
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            if '409' in str(e):
                print('⚠️ Detectado conflito 409 - Reiniciando em 5s...')
                time.sleep(5)
                bot.remove_webhook()
                time.sleep(1)
            else:
                print(f'⚠️ Erro: {str(e)}')
                time.sleep(15)
