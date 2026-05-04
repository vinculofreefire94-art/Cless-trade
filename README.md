# 🤖 Cless Trade - Bot Elite de Trading

Bot profissional de análise técnica do Bitcoin para Telegram com integração Railway.

## 📋 Características

✅ **Análise Multi-Timeframe**: 1H + 4H com confluência  
✅ **Indicadores Técnicos**: RSI, ADX, ATR, EMA, MACD  
✅ **Gráficos Profissionais**: Charts com mplfinance  
✅ **Cotações em Múltiplas Moedas**: USD, EUR, USDC  
✅ **Notícias de Cripto**: Feed RSS em tempo real  
✅ **Scheduler Automático**: 30min para sinais, 2h para notícias  
✅ **Comandos Telegram**: /btc, /news, /status, /ajuda

## 🚀 Deploy no Railway

### Pré-requisitos
- Conta no [Railway](https://railway.app)
- Repositório GitHub com estes arquivos
- Token do bot Telegram e Chat ID

### Passos de Deploy

1. **Acesse** https://railway.app e faça login
2. **Clique** em "New Project" → "Deploy from GitHub"
3. **Selecione** o repositório `cless-trade`
4. **Aguarde** o railway detectar `Procfile`
5. **Configure** as variáveis de ambiente:
   ```
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   TELEGRAM_CHAT_ID=seu_chat_id_aqui
   ```
6. **Deploy**: Clique em "Deploy" e aguarde ~2 minutos

### Variáveis de Ambiente

| Variável | Valor | Exemplo |
|----------|-------|----------|
| `TELEGRAM_BOT_TOKEN` | Token do bot | `8601631701:AAGAIRh1UfLXP3yyMy-pU6jyYe1Da6d2hwQ` |
| `TELEGRAM_CHAT_ID` | ID do chat/grupo | `-1003780528406` |

## 📱 Comandos Disponíveis

```
/btc    - Gera análise imediata do Bitcoin
/news   - Busca última notícia cripto
/status - Mostra status do sistema
/ajuda  - Exibe este menu
```

## 📊 Funcionamento

### Sinais de Trading (A cada 30 minutos)
1. Coleta análise 1H + 4H do TradingView
2. Valida confluência entre timeframes
3. Verifica ADX >= 20 (tendência)
4. Calcula TP/SL com base no ATR
5. Envia gráfico + recomendação

### Notícias (A cada 2 horas)
1. Busca feed RSS Cointelegraph
2. Filtra notícias únicas
3. Envia com link e resumo

## 🛠️ Testes Locais

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
echo "TELEGRAM_BOT_TOKEN=seu_token" > .env
echo "TELEGRAM_CHAT_ID=seu_id" >> .env

# Executar
python bot.py
```

## ⚠️ Avisos Importantes

- ⚡ O bot usa APIs gratuitas (podem ter delays)
- 🔐 **NUNCA** faça commit do token (use `.env`)
- 📊 Sinais são educacionais, não são recomendação de investimento
- 💰 Trade com cuidado e respeite sua gestão de risco

## 📝 Estrutura do Código

```
cless-trade/
├── bot.py                 # Código principal
├── requirements.txt        # Dependências Python
├── Procfile               # Config para Railway
├── runtime.txt            # Versão Python
├── .env.example           # Template de env
└── README.md              # Este arquivo
```

## 🔧 Troubleshooting

### Bot não responde
```bash
# Verifique logs no Railway
railway logs

# Teste token localmente
python -c "import telebot; bot = telebot.TeleBot('TOKEN'); print(bot.get_me())"
```

### Erro de dependências
```bash
# Reinstale
pip install --upgrade -r requirements.txt
```

### Gráficos não aparecem
- Verifique permissões de escrita em `/tmp`
- Aumente limite de memória no Railway

## 📧 Suporte

Para problemas:
1. Verifique os logs do Railway
2. Valide o token Telegram
3. Confirme que o chat ID é correto

---

**Desenvolvido com ❤️ para traders profissionais**
