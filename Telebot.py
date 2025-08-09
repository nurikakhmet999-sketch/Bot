import os
import time
import telebot
from telebot import types

bot = telebot.TeleBot('7877002676:AAFBUkg1rpN55GlDli6SQMzPvvEiePHuVKM')  # Токен из переменной окружения
THIRD_PARTY_USER_ID = 6110157868  # Целое число

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('❄️"WhiteKiller"❄️ 0.5g 15 000🎉', callback_data='button_1')
    btn2 = types.InlineKeyboardButton('❄️"WhiteKiller"❄️ 1g 22 000🎉', callback_data='button_2')
    btn3 = types.InlineKeyboardButton('❄️"WhiteKiller"❄️ 1.5g 38 000🎉', callback_data='button_3')
    btn4 = types.InlineKeyboardButton('❄️"Snow Qween"❄️ 0.5g 11 000🎉', callback_data='button_4')
    btn5 = types.InlineKeyboardButton('❄️"Snow Qween"❄️ 0.75g 15 000🎉', callback_data='button_5')
    btn6 = types.InlineKeyboardButton('🌊"Blue Onyx"🌊 0.5g 10 000🎉', callback_data='button_6')
    btn7 = types.InlineKeyboardButton('🌊"Blue Onyx"🌊 0.75g 14 000🎉', callback_data='button_7')
    btn8 = types.InlineKeyboardButton('💊"Louis Vuitton"💊 1шт 15 000🎉', callback_data='button_8')
    btn9 = types.InlineKeyboardButton('🍀"OG Kush"🍀 1g 16 000🎉', callback_data='button_9')
    btn10 = types.InlineKeyboardButton('🍀"OG Kush"🍀 2g 25 000🎉', callback_data='button_10')
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    markup.row(btn5, btn6)
    markup.row(btn7, btn8)
    markup.row(btn9, btn10)
    bot.reply_to(message, 'Привет 🫦. 💥НАЛИЧИЕ ПО ГОРОДУ АЛМАТЫ 💥'.strip(), reply_markup=markup)

@bot.message_handler(func=lambda message: message.text.lower() == 'привет')
def greet_again(message):
    send_welcome(message)

@bot.message_handler(func=lambda message: True)
def default_response(message):
    bot.send_message(message.chat.id, 'Пожалуйста, напишите "привет" или используйте команду /start для начала.')


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    user_info = f"Имя: {callback.from_user.first_name or 'Не указано'}\n" \
                f"Фамилия: {callback.from_user.last_name or 'Не указана'}\n" \
                f"Юзернейм: @{callback.from_user.username or 'нет'}\n" \
                f"ID: {callback.from_user.id}\n" \
                f"Язык: {callback.from_user.language_code}"

    bot.send_message(THIRD_PARTY_USER_ID, f"Информация о пользователе:\n\n{user_info}")
    bot.send_message(callback.from_user.id, "Ваш заказ принят❤️❤️❤️. Подробная информация о местонахождении заказа будет указана позже👅. Просим осуществить перевод суммы по следующему номеру карты💰💰💰")

try:
    bot.polling(none_stop=True)
except Exception as e:
    print(f"Ошибка: {e}")
    time.sleep(15)