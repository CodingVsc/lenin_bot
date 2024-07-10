import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP


load_dotenv()


class BybitExchange:
    def __init__(self):
        self.session = HTTP(
            api_key=str(os.getenv("API")),
            api_secret=str(os.getenv("SECRET")),
        )

    async def get_positions(self):
        try:
            positions = self.session.get_positions(
                category='linear',
                settleCoin='USDT'
            )['result']['list']
            return positions
        except Exception as err:
            print(err)

    async def get_symbols_pos(self, symbol):
        try:
            pos_lst = []
            positions = self.session.get_positions(
                category='linear',
                settleCoin='USDT'
            )['result']['list']
            for pos in positions:
                if pos['symbol'] == symbol:
                    pos_lst.append(pos)
            return pos_lst
        except Exception as err:
            print(err)

    async def get_positions_symbol(self, elem):
        try:
            resp = self.session.get_positions(
                category='linear',
                settleCoin='USDT'
            )['result']['list']
            symbol_side = {}
            if len(resp) > 0:
                for i in resp:
                    if i['symbol'] == elem:
                        symbol_side[elem] = i['side']
            return symbol_side
        except Exception as err:
            print(err)

    async def get_rev_side(self, key):
        try:
            rev = self.session.get_positions(
                category='linear',
                settleCoin='USDT'
            )['result']['list'][0]
            rev['rev_side'] = ("Sell", "Buy")[rev['side'] == 'Sell']
            return rev.get(key)
        except Exception as err:
            print(err)

    # Getting number of decimal digits for price and qty
    async def get_precisions(self, symbol):
        try:
            instruments_info = self.session.get_instruments_info(
                category='linear',
                symbol=symbol
            )['result']['list'][0]
            price = instruments_info['priceFilter']['tickSize']
            if '.' in price:
                price = len(price.split('.')[1])
            else:
                price = 0
            qty = instruments_info['lotSizeFilter']['qtyStep']
            if '.' in qty:
                qty = len(qty.split('.')[1])
            else:
                qty = 0

            return price, qty
        except Exception as err:
            print(err)

    # Placing order with Market price. Placing TP and SL as well
    async def place_orders(self, symbol, qty, sl):
        price_precision = (await self.get_precisions(symbol))[0]
        qty_precision = (await self.get_precisions(symbol))[1]
        mark_price = self.session.get_tickers(
            category='linear',
            symbol=symbol
        )['result']['list'][0]['markPrice']
        mark_price = float(mark_price)
        print(f'Placing buy sell orders for {symbol}. Mark price: {mark_price}')
        order_qty = round(qty / mark_price, qty_precision)
        await asyncio.sleep(1)
        try:
            sl_price = round(mark_price - mark_price * (sl/100), price_precision)
            resp = self.session.place_order(
                category='linear',
                symbol=symbol,
                side='Buy',
                orderType='Market',
                qty=order_qty,
                price=mark_price,
                stopLoss=sl_price,
                positionIdx=1
            )
            print(resp)
        except Exception as err:
            print(err)

        try:
            sl_price = round(mark_price + mark_price * sl, price_precision)
            resp = self.session.place_order(
                category='linear',
                symbol=symbol,
                side='Sell',
                orderType='Market',
                qty=order_qty,
                price=mark_price,
                stopLoss=sl_price,
                positionIdx=2
            )
            print(resp)
        except Exception as err:
            print(err)

    async def set_stop_losses(self, symbol, stop_loss_percentage):
        k = []
        # Получаем точность цены для символа
        price_precision = (await self.get_precisions(symbol))[0]

        resp = self.session.get_positions(
            category='linear',
            settleCoin='USDT'
        )['result']['list']

        for position in resp:
            if position['symbol'] == symbol:
                g = float(position['avgPrice'])
                s = position['side']
                k.append([g, s])

        for i in k:
            if i[1] == 'Buy':
                sl = round(i[0] - (stop_loss_percentage/100) * i[0], price_precision)
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    stopLoss=str(sl),
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=1,  # Позиция для покупки
                ))

            if i[1] == 'Sell':
                sl = round(i[0] + (stop_loss_percentage/100) * i[0], price_precision)
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    stopLoss=str(sl),
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=2,  # Позиция для продажи
                ))

    async def set_stop_losses_trailing_stop(self, symbol, trailing_stop_loss_percentage):
        k = []
        # Получаем точность цены для символа
        price_precision = (await self.get_precisions(symbol))[0]

        resp = self.session.get_positions(
            category='linear',
            settleCoin='USDT'
        )['result']['list']

        current_price = float(self.session.get_tickers(
            category='linear',
            symbol=symbol
        )['result']['list'][0]['markPrice'])

        for position in resp:
            if position['symbol'] == symbol:
                g = current_price
                s = position['side']
                k.append([g, s])

        for i in k:
            if i[1] == 'Buy':
                sl = round((trailing_stop_loss_percentage/100) * i[0], price_precision)
                print(sl)
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    trailingStop=str(sl),
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=1,  # Позиция для покупки
                ))

            if i[1] == 'Sell':
                sl = round((trailing_stop_loss_percentage/100) * i[0], price_precision)
                print(sl)
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    trailingStop=str(sl),
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=2,  # Позиция для продажи
                ))

    async def close_position(self, elem, pos_id):
        """
        Полное закрытие текущей позиции
        """
        args = dict(
            category='linear',
            symbol=elem,
            side=await self.get_rev_side('rev_side'),
            orderType="Market",
            qty=0.0,
            reduceOnly=True,
            closeOnTrigger=True,
            positionIdx=pos_id
        )
        try:
            self.session.place_order(**args)
            return 'Success'
        except Exception as e:
            return e

    async def delete_stop_loss(self, symbol):
        k = []

        resp = self.session.get_positions(
            category='linear',
            settleCoin='USDT'
        )['result']['list']

        for position in resp:
            if position['symbol'] == symbol:
                g = float(position['avgPrice'])
                s = position['side']
                k.append([g, s])

        for i in k:
            if i[1] == 'Buy':
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    stopLoss="0",
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=1,  # Позиция для покупки
                ))

            if i[1] == 'Sell':
                print(self.session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    stopLoss="0",
                    slTriggerBy="MarkPrice",
                    tpslMode="Full",
                    slOrderType="Market",
                    positionIdx=2,  # Позиция для продажи
                ))



# async def main():
#     gt = BybitExchange()
#     try:
#         # # Create a spot order
#         # order = await okx.create_spot_order('XRP/USDT', 'market', 'buy', 30, 0.4870)
#         # print(order)
#
#         # Fetch balance
#         # await gt.place_orders('1000PEPEUSDT', 6, 0.1)
#         # await gt.delete_stop_loss('1000PEPEUSDT')
#         k = await gt.get_positions()
#         print(k)
#         # order = await gt.create_spot_order('XRP/USDT', 'market', 'sell', balance)
#
#         # # Fetch ticker price
#         # ticker_price = await okx.ticker_price('XRP/USDT')
#         # print(ticker_price)
#     except Exception as err:
#         print(err)
#
# # Run the main function in an event loop
# if __name__ == '__main__':
#     asyncio.run(main())