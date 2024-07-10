import os
import time
import telebot
import logging
import asyncio
from threading import Thread

from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from exchange import BybitExchange

# Configure logging
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

load_dotenv()

class BybitBot:
    def __init__(self):
        self.exchange = BybitExchange()
        self.symbols = []
        self.trade_size = 6
        self.stop_loss_percentage = 1
        self.trailing_stop_percentage = 1
        self.position_duration = 10
        self.open_positions = {}

    async def open_initial_positions(self):
        while True:
            if len(self.symbols) > 0:
                try:
                    for symbol in self.symbols:
                        all_pos = await self.exchange.get_symbols_pos(symbol)
                        if len(all_pos) == 0:
                            await self.exchange.place_orders(symbol, self.trade_size, self.stop_loss_percentage)
                            self.open_positions[symbol] = {'stop_loss_set': False}
                        await asyncio.sleep(10)
                except Exception as e:
                    print(e)

    async def monitor_positions(self):
        while True:
            try:
                for symbol in list(self.open_positions.keys()):
                    positions = await self.exchange.get_symbols_pos(symbol)
                    if not self.open_positions[symbol]['stop_loss_set'] and len(positions) == 2:
                        await self.exchange.set_stop_losses(symbol, self.stop_loss_percentage)
                        self.open_positions[symbol]['stop_loss_set'] = True
                    if len(positions) == 1:
                        await self.exchange.delete_stop_loss(symbol)
                        await self.exchange.set_stop_losses_trailing_stop(symbol, self.trailing_stop_percentage)
                        await asyncio.sleep(self.position_duration)
                        await self.exchange.close_position(symbol, positions[0]['positionIdx'])
                        self.open_positions.pop(symbol)
                await asyncio.sleep(1)
            except Exception as e:
                print(e)
            await asyncio.sleep(1)

    async def start(self):
        await asyncio.gather(self.open_initial_positions(), self.monitor_positions())

    def update_parameters(self, user_messages):
        self.symbols = user_messages.get('coins_pair', self.symbols)
        self.trade_size = user_messages.get('take_profit', self.trade_size)
        self.stop_loss_percentage = user_messages.get('stop_loss', self.stop_loss_percentage)
        self.trailing_stop_percentage = user_messages.get('trailing_stop_percentage', self.trailing_stop_percentage)
        self.position_duration = user_messages.get('position_duration', self.position_duration)
        print(f"Updated parameters:"
              f"{self.symbols}, {self.trade_size}, {self.stop_loss_percentage}, {self.trailing_stop_percentage}, "
              f"{self.position_duration}")


class TGTradingBot:
    def __init__(self, token, monitor):
        logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.bot = telebot.TeleBot(token)
        self.monitor = monitor
        self.user_messages = {}
        self.user_states = {}
        self.chat_id = 7348443729

        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(commands=['coins_pair'])(self.handle_set_coins)
        self.bot.message_handler(commands=['stop_loss'])(self.handle_stop_loss)
        self.bot.message_handler(commands=['trade_size'])(self.handle_set_trade_size)
        self.bot.message_handler(commands=['trailing_stop_percentage'])(self.handle_set_trailing_stop_percentage)
        self.bot.message_handler(commands=['position_duration'])(self.handle_set_position_duration)
        self.bot.message_handler(commands=['stop_bot'])(self.handle_stop_bot)

        self.bot.message_handler(func=lambda message: True)(self.handle_text_message)
        self.bot.callback_query_handler(func=lambda call: True)(self.callback_query)

    def update_user_state(self, chat_id, new_state):
        self.user_states[chat_id] = new_state

    def get_user_state(self, chat_id):
        return self.user_states.get(chat_id, 'start')

    def handle_start(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'start')
            self.bot.send_message(self.chat_id, "Указать монеты: /coins_pair; "
                                              "\nстоп лосс: /stop_loss; \ntrailing stop: /trailing_stop_percentage; "
                                              "\nвремя открытой сделки: /position_duration"
                                              "\nУстановить размер депозита на каждую сделку: /trade_size; "
                                              "\nОстановить бота: /stop_bot",
                                  reply_markup=self.get_update_button())

    def handle_set_coins(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'coins_pair')
            self.bot.send_message(self.chat_id, "Выберите монеты на которых "
                                          "будете торговать. Запишите через пробел как в образце"
                                          "\n обязательно используйте только такой формат записи монет"
                                          "\n(например: DOGEUSDT 1000PEPEUSDT BTCUSDT ETHUSDT):")

    def handle_stop_bot(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'stop_bot')
            self.bot.send_message(self.chat_id, "Для остановки бота и продолжения мониторинга отправьте "
                                              "любой текст и нажмите "
                                              "`Обновить параметры`")


    def handle_stop_loss(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'stop_loss')
            self.bot.send_message(self.chat_id, "Введите стоп лосс (%):")

    def handle_set_trade_size(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'trade_size')
            self.bot.send_message(self.chat_id, "Введите размер депозита который вы хотите использовать для каждой монеты в USDT:")

    def handle_set_trailing_stop_percentage(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'trailing_stop_percentage')
            self.bot.send_message(self.chat_id, "Введите процент trailing stop(%):")

    def handle_set_position_duration(self, message):
        chat_id = message.chat.id
        if chat_id == self.chat_id:
            self.update_user_state(self.chat_id, 'position_duration')
            self.bot.send_message(self.chat_id, "Введите время в секундах на которое будет "
                                                "открыто прибыльное направление после закрытия убыточного:")

    def handle_text_message(self, message):
        chat_id = message.chat.id
        user_state = self.get_user_state(chat_id)

        if user_state == 'coins_pair':
            text = message.text
            if chat_id == self.chat_id:
                exch_lst = text.split()
                self.user_messages['coins_pair'] = exch_lst
                self.bot.send_message(self.chat_id, f"Ваш выбор '{text}' сохранен.")


        if user_state == 'stop_bot':
            text = message.text
            if chat_id == self.chat_id:
                self.user_messages['coins_pair'] = []
                self.bot.send_message(self.chat_id, f"Теперь нажмите обновить параметры.")


        if user_state == 'stop_loss':
            text = message.text
            if chat_id == self.chat_id:
                self.user_messages['stop_loss'] = float(text)
                self.bot.send_message(self.chat_id, f"Ваш выбор '{text}' сохранен.")

        if user_state == 'trade_size':
            text = message.text
            if chat_id == self.chat_id:
                self.user_messages['trade_size'] = float(text)
                self.bot.send_message(self.chat_id, f"Ваш выбор '{text}' сохранен.")

        if user_state == 'trailing_stop_percentage':
            text = message.text
            if chat_id == self.chat_id:
                self.user_messages['trailing_stop_percentage'] = float(text)
                self.bot.send_message(self.chat_id, f"Ваш выбор '{text}' сохранен.")

        if user_state == 'position_duration':
            text = message.text
            if chat_id == self.chat_id:
                self.user_messages['position_duration'] = float(text)
                self.bot.send_message(self.chat_id, f"Ваш выбор '{text}' сохранен.")

    def get_update_button(self):
        markup = InlineKeyboardMarkup()
        button = InlineKeyboardButton("Обновить параметры", callback_data="update_parameters")
        markup.add(button)
        return markup

    def callback_query(self, call):
        if call.data == "update_parameters":
            self.monitor.update_parameters(self.user_messages)
            self.bot.send_message(call.message.chat.id, "Параметры успешно обновлены!")

    def run(self):
        while True:
            try:
                self.bot.polling(none_stop=True, interval=0, timeout=20)
            except ConnectionError as e:
                logging.error(f"ConnectionError: {e}")
                time.sleep(15)
            except Exception as e:
                logging.exception("Unexpected error: %s", e)
                time.sleep(15)


async def main():
    monitor = BybitBot()
    bot = TGTradingBot(str(os.getenv('TG_TOKEN')), monitor)

    bot_thread = Thread(target=bot.run)
    bot_thread.start()

    await monitor.start()

if __name__ == '__main__':
    asyncio.run(main())
