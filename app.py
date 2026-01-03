
from flask import Flask, render_template, jsonify, request
from binance.client import Client
from binance.exceptions import BinanceAPIException
from threading import Thread
from decimal import Decimal, ROUND_DOWN, getcontext
import time

# precisão decimal
getcontext().prec = 18

# ---------------------------
# CONFIG (coloque suas chaves)
# ---------------------------

API_KEY = 'LoJrWtBxkif6NRn4Wqvsg0Nb47CmaAot0k6YCsq9GknapqyldAOzaOi1FZMTCXWG'
API_SECRET = '0yl1DZ2cTIuBuXQIRA4qlfikH0nIPCqrBlBBOKlrDgKsH2SWqdoGjELeBffDrKpi'
client = Client(API_KEY, API_SECRET)
app = Flask(__name__)

# ---------------------------
# PAR / PARAMS
# ---------------------------
PAIR = "SOLUSDT"
USE_USDT_PCT = Decimal("1.0")     # 100% do saldo USDT
FEE_MARGIN = Decimal("0.99")      # deixa 1% para taxas
TAKE_PROFIT_PCT = Decimal("0.03") # +3%
STOP_LOSS_PCT = Decimal("0.02")   # -2%
RSI_PERIOD = 14
MA_SHORT = 9
MA_LONG = 21

# memória volátil
historico = []
erros = []
positions = []

BOT_ATIVO = False

# ---------------------------
# UTILIDADES BINANCE (LOT/NOTIONAL)
# ---------------------------
def get_symbol_info(pair=PAIR):
    return client.get_symbol_info(pair)

def get_filters(pair=PAIR):
    info = get_symbol_info(pair)
    f = {}
    for fil in info.get("filters", []): 
        f[fil["filterType"]] = fil
    return f

def get_min_notional(pair=PAIR):
    f = get_filters(pair)
    notional = f.get("NOTIONAL", {}).get("minNotional")
    return Decimal(str(notional)) if notional is not None else Decimal("5")

def get_step_size(pair=PAIR):
    f = get_filters(pair)
    step = f.get("LOT_SIZE", {}).get("stepSize")
    return Decimal(str(step)) if step is not None else Decimal("0.000001")

def adjust_quantity_to_step(qty, step_size):
    """Ajusta quantidade para o step size (arredonda para baixo)."""
    qty_dec = Decimal(str(qty))
    step_dec = Decimal(str(step_size))
    if step_dec == 0:
        return float(qty_dec)
    n = (qty_dec // step_dec)
    adj = (n * step_dec).quantize(step_dec, rounding=ROUND_DOWN)
    return float(adj)

def adjust_usdt_precision(usdt):
    """Garante no máximo 2 casas decimais para quoteOrderQty (evita -1111)."""
    usdt_dec = Decimal(str(usdt))
    adj = usdt_dec.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return float(adj)

# ---------------------------
# MARKET DATA / INDICADORES
# ---------------------------
def fetch_klines(pair=PAIR, interval="1m", limit=200):
    klines = client.get_klines(symbol=pair, interval=interval, limit=limit)
    closes = [float(k[4]) for k in klines]
    return closes

def simple_ma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def rsi(values, period=RSI_PERIOD):
    if len(values) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, period+1):
        diff = values[-(period+1)+i] - values[-(period+1)+i -1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain/avg_loss
    return 100 - (100 / (1 + rs))

# ---------------------------
# ORDERS helpers
# ---------------------------
def market_buy_with_usdt(usdt_amount):
    """
    Compra usando quoteOrderQty (gasta USDT). Ajusta precisão do valor.
    """
    min_not = get_min_notional(PAIR)
    usdt_adj = Decimal(str(usdt_amount))
    if usdt_adj < min_not:
        raise ValueError(f"Valor em USDT ({usdt_amount}) menor que minNotional {min_not}")
    # ajusta precision para evitar -1111
    q = adjust_usdt_precision(usdt_adj)
    return client.order_market_buy(symbol=PAIR, quoteOrderQty=str(q))

def market_sell_quantity(quantity):
    """
    Ajusta quantity ao stepSize e faz sell.
    """
    step = get_step_size(PAIR)
    adj_qty = adjust_quantity_to_step(quantity, step)
    if adj_qty <= 0:
        raise ValueError("Quantidade ajustada <= 0 (muito pequena para o step size).")
    return client.order_market_sell(symbol=PAIR, quantity=str(adj_qty))

# ---------------------------
# POSIÇÕES e HISTÓRICO
# ---------------------------
def open_position(entry_price, qty, order_info):
    take_price = entry_price * (1 + float(TAKE_PROFIT_PCT))
    stop_price = entry_price * (1 - float(STOP_LOSS_PCT))
    pos = {
        "entry_price": entry_price,
        "quantity": qty,
        "take_price": take_price,
        "stop_price": stop_price,
        "opened_at": time.time(),
        "order": order_info
    }
    positions.append(pos)
    historico.append({
        "action": "BUY",
        "price": entry_price,
        "qty": qty,
        "time": time.time()
    })

def close_position(pos, exit_price, order_info, reason="take/stop/strategy"):
    historico.append({
        "action": "SELL",
        "price": exit_price,
        "qty": pos["quantity"],
        "time": time.time(),
        "reason": reason
    })
    if pos in positions:
        positions.remove(pos)

# ---------------------------
# ESTRATÉGIA (MA + RSI)
# ---------------------------
def strategy_should_buy(closes):
    if len(closes) < MA_LONG + 2:
        return False, {}
    ma_short_prev = simple_ma(closes[:-1], MA_SHORT)
    ma_long_prev = simple_ma(closes[:-1], MA_LONG)
    ma_short = simple_ma(closes, MA_SHORT)
    ma_long = simple_ma(closes, MA_LONG)
    r = rsi(closes, RSI_PERIOD) or 50
    cross = False
    if ma_short_prev and ma_long_prev and ma_short and ma_long:
        cross = (ma_short_prev <= ma_long_prev) and (ma_short > ma_long)
    return (cross or (r < 32)), {"ma_short": ma_short, "ma_long": ma_long, "rsi": r}

def strategy_should_sell(closes, pos):
    price_now = closes[-1]
    r = rsi(closes, RSI_PERIOD) or 50
    ma_short = simple_ma(closes, MA_SHORT)
    ma_long = simple_ma(closes, MA_LONG)
    death_cross = False
    if len(closes) >= MA_LONG + 2:
        ma_short_prev = simple_ma(closes[:-1], MA_SHORT)
        ma_long_prev = simple_ma(closes[:-1], MA_LONG)
        if ma_short_prev and ma_long_prev and ma_short and ma_long:
            death_cross = (ma_short_prev >= ma_long_prev) and (ma_short < ma_long)
    if price_now >= pos["take_price"]:
        return True, "take_profit", {"price": price_now, "rsi": r}
    if price_now <= pos["stop_price"]:
        return True, "stop_loss", {"price": price_now, "rsi": r}
    if death_cross or r > 68:
        return True, "strategy_sell", {"price": price_now, "rsi": r}
    return False, None, {"price": price_now, "rsi": r}

# ---------------------------
# BOT LOOP
# ---------------------------
def bot_loop():
    global BOT_ATIVO
    print("Bot PRO loop started.")
    while True:
        try:
            if BOT_ATIVO:
                closes = fetch_klines(PAIR, interval="1m", limit=200)
                price_now = closes[-1]

                buy_signal, meta_buy = strategy_should_buy(closes)

                # open position if none and buy signal
                if len(positions) == 0 and buy_signal:
                    # compute USDT available
                    usdt_bal = Decimal(str(client.get_asset_balance(asset="USDT")["free"]))
                    use_amount = (usdt_bal * USE_USDT_PCT) * FEE_MARGIN
                    min_not = get_min_notional(PAIR)
                    if use_amount < min_not:
                        erros.append({"type": "compra", "error": f"usdt {use_amount} < minNotional {min_not}"})
                    else:
                        try:
                            order = market_buy_with_usdt(float(use_amount))
                            fills = order.get("fills", [])
                            if fills:
                                qty = sum([float(f.get("qty", 0)) for f in fills])
                                price = float(fills[-1].get("price", price_now))
                            else:
                                qty = float(order.get("executedQty", 0) or 0)
                                price = price_now
                            if qty > 0:
                                open_position(price, qty, order)
                            else:
                                erros.append({"type": "compra", "error": "executed qty = 0"})
                        except Exception as e:
                            erros.append({"type": "compra", "error": str(e)})

                # monitor positions
                for pos in positions[:]:
                    sell_flag, reason, meta = strategy_should_sell(closes, pos)
                    if sell_flag:
                        try:
                            qty_to_sell = pos["quantity"]
                            order = market_sell_quantity(qty_to_sell)
                            close_position(pos, closes[-1], order, reason=reason)
                        except Exception as e:
                            erros.append({"type": "venda", "error": str(e)})
            # sleep cycle
        except Exception as e:
            erros.append({"type": "bot_loop", "error": str(e)})
        time.sleep(5)

# inicia thread do bot (daemon)
thread = Thread(target=bot_loop, daemon=True)
thread.start()

# ---------------------------
# FLASK ROUTES
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/bot/ativar", methods=["POST"])
def api_ativar():
    global BOT_ATIVO
    BOT_ATIVO = True
    return jsonify({"status": "ativado"})

@app.route("/bot/desativar", methods=["POST"])
def api_desativar():
    global BOT_ATIVO
    BOT_ATIVO = False
    return jsonify({"status": "desativado"})

@app.route("/bot_status")
def api_status():
    return jsonify({"ativo": BOT_ATIVO})

@app.route("/preco/<pair>")
def api_preco(pair):
    try:
        p = client.get_symbol_ticker(symbol=pair)
        return jsonify(p)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/saldo")
def api_saldo():
    try:
        sol = client.get_asset_balance(asset="SOL")
        usdt = client.get_asset_balance(asset="USDT")
        return jsonify({"SOL": sol, "USDT": usdt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/historico")
def api_hist():
    return jsonify(historico)

@app.route("/erros")
def api_erros():
    return jsonify(erros)

@app.route("/positions")
def api_positions():
    return jsonify(positions)

# run
if __name__ == "__main__":
    app.run(debug=True)
