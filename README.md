🤖 Trading Bot Binance com Flask (MA + RSI)

Este projeto é um bot de trade automático para a Binance, desenvolvido em Python, que utiliza uma estratégia simples baseada em Médias Móveis (MA) e RSI, com controle de Take Profit e Stop Loss.
O bot possui uma API web em Flask para ativar/desativar o bot e consultar status, saldo, posições, histórico e erros.

⚠️ Aviso: Este código é educacional. Operar na Binance envolve riscos financeiros reais.

🚀 Funcionalidades

✅ Compra e venda automática no mercado (Market Order)

✅ Estratégia baseada em:

Cruzamento de Médias Móveis (MA 9 e MA 21)

RSI (14 períodos)

✅ Take Profit e Stop Loss automáticos

✅ Respeita regras da Binance:

minNotional

stepSize

Precisão de casas decimais

✅ Uso de 100% do saldo USDT configurável

✅ API REST com Flask para controle do bot

✅ Execução contínua em thread separada

✅ Histórico de operações e log de erros

🧠 Estratégia Utilizada
📈 Compra (BUY)

O bot compra quando uma das condições abaixo é atendida:

Cruzamento de alta:

MA curta (9) cruza para cima da MA longa (21)

RSI abaixo de 32 (possível sobrevenda)

📉 Venda (SELL)

O bot vende quando qualquer condição abaixo acontece:

🎯 Take Profit: +3% (configurável)

🛑 Stop Loss: -2% (configurável)

❌ Cruzamento de baixa (MA 9 cruza para baixo da MA 21)

⚠️ RSI acima de 68 (possível sobrecompra)

⚙️ Configurações Principais

No início do código:

API_KEY = ''
API_SECRET = ''


⚠️ Nunca compartilhe suas chaves da Binance.

Parâmetros da estratégia:

PAIR = "SOLUSDT"
USE_USDT_PCT = Decimal("1.0")     # 100% do saldo USDT
FEE_MARGIN = Decimal("0.99")      # Reserva 1% para taxas
TAKE_PROFIT_PCT = Decimal("0.03") # 3% de lucro
STOP_LOSS_PCT = Decimal("0.02")   # 2% de prejuízo
RSI_PERIOD = 14
MA_SHORT = 9
MA_LONG = 21

🧩 Estrutura do Projeto
📦 projeto
 ┣ 📜 app.py              # Código principal do bot
 ┣ 📂 templates
 ┃ ┗ 📜 index.html        # Interface web (opcional)
 ┗ 📜 README.md

🌐 Rotas da API (Flask)
🔘 Controle do Bot
Rota	Método	Descrição
/bot/ativar	POST	Ativa o bot
/bot/desativar	POST	Desativa o bot
/bot_status	GET	Retorna se o bot está ativo
📊 Informações
Rota	Método	Descrição
/preco/SOLUSDT	GET	Preço atual do par
/saldo	GET	Saldo de SOL e USDT
/positions	GET	Posições abertas
/historico	GET	Histórico de trades
/erros	GET	Log de erros
▶️ Como Executar
1️⃣ Instale as dependências
pip install flask python-binance

2️⃣ Configure suas chaves da Binance
API_KEY = 'SUA_API_KEY'
API_SECRET = 'SUA_API_SECRET'

3️⃣ Execute o bot
python app.py

4️⃣ Acesse no navegador
http://127.0.0.1:5000

🔄 Funcionamento Interno

O bot roda em loop a cada 5 segundos

Busca candles de 1 minuto

Só abre uma posição por vez

Executa ordens Market

Ajusta automaticamente:

Quantidade (stepSize)

Valor mínimo (minNotional)

Precisão de USDT (evita erro -1111 da Binance)

⚠️ Avisos Importantes

❗ Use conta TESTNET da Binance para testes

❗ Nunca opere sem entender a estratégia

❗ Este bot não garante lucro

❗ Mercado de criptomoedas é altamente volátil

📌 Próximas Melhorias (Sugestões)

Trailing Stop

Suporte a múltiplos pares

Backtest da estratégia

Interface gráfica mais completa

Modo paper trade (simulação)

Se quiser, posso:

🔧 Melhorar a estratégia

📊 Criar um painel estilo Binance

🧪 Adicionar backtest

🛡️ Converter para Testnet

🧠 Explicar o código linha por linha
