# -*- coding: utf-8 -*-

import os
from flask import request, flash, url_for, redirect, session, make_response
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
import requests
from pymongo import MongoClient
import mimetypes
from random import randint
from flask_babel import Babel, gettext, lazy_gettext
import datetime
#import uuid
#from ft import send_mail

from keys import FLASK_SECRET_KEY, TG_TOKEN, DF_TOKEN, GOOGLE_MAPS_API_KEY, MAIL_PWD

VALID_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".JPG",
    ".JPEG",
    ".PNG",
    ".GIF",
    ".BMP"
]

VALID_IMAGE_MIMETYPES = [
    "image"
]

LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français',
    'uk': 'Українська'
}

COUNTRIES_CODES_NAMES = [{'Code': 'AF', 'Name': {'ru': 'Афганистан', 'uk': 'Афганістан', 'en': 'Afghanistan'}}, {'Code': 'AX', 'Name': {'ru': 'Аландские острова', 'uk': 'Аландскі острови', 'en': 'Åland Islands'}}, {'Code': 'AL', 'Name': {'ru': 'Албания', 'uk': 'Албанія', 'en': 'Albania'}}, {'Code': 'DZ', 'Name': {'ru': 'Алжир', 'uk': 'Алжир', 'en': 'Algeria'}}, {'Code': 'AS', 'Name': {'ru': 'Американское Самоа', 'uk': 'Американське Самоа', 'en': 'American Samoa'}}, {'Code': 'AD', 'Name': {'ru': 'Андорра', 'uk': 'Андорра', 'en': 'Andorra'}}, {'Code': 'AO', 'Name': {'ru': 'Ангола', 'uk': 'Ангола', 'en': 'Angola'}}, {'Code': 'AI', 'Name': {'ru': 'Ангилья', 'uk': 'Ангілья', 'en': 'Anguilla'}}, {'Code': 'AQ', 'Name': {'ru': 'Антарктика', 'uk': 'Антарктика', 'en': 'Antarctica'}}, {'Code': 'AG', 'Name': {'ru': 'Антигуа и Барбуда', 'uk': 'Антигуа і Барбуда', 'en': 'Antigua and Barbuda'}}, {'Code': 'AR', 'Name': {'ru': 'Аргентина', 'uk': 'Аргентина', 'en': 'Argentina'}}, {'Code': 'AM', 'Name': {'ru': 'Армения', 'uk': 'Арменія', 'en': 'Armenia'}}, {'Code': 'AW', 'Name': {'ru': 'Аруба', 'uk': 'Аруба', 'en': 'Aruba'}}, {'Code': 'AU', 'Name': {'ru': 'Австралия', 'uk': 'Австралія', 'en': 'Australia'}}, {'Code': 'AT', 'Name': {'ru': 'Австрия', 'uk': 'Австрія', 'en': 'Austria'}}, {'Code': 'AZ', 'Name': {'ru': 'Азербайджан', 'uk': 'Азербайджан', 'en': 'Azerbaijan'}}, {'Code': 'BS', 'Name': {'ru': 'Багамы', 'uk': 'Багами', 'en': 'Bahamas'}}, {'Code': 'BH', 'Name': {'ru': 'Бахрейн', 'uk': 'Бахрейн', 'en': 'Bahrain'}}, {'Code': 'BD', 'Name': {'ru': 'Бангладеш', 'uk': 'Бангладеш', 'en': 'Bangladesh'}}, {'Code': 'BB', 'Name': {'ru': 'Барбадос', 'uk': 'Барбадос', 'en': 'Barbados'}}, {'Code': 'BY', 'Name': {'ru': 'Беларусь', 'uk': 'Білорусь', 'en': 'Belarus'}}, {'Code': 'BE', 'Name': {'ru': 'Бельгия', 'uk': 'Бельгія', 'en': 'Belgium'}}, {'Code': 'BZ', 'Name': {'ru': 'Белиз', 'uk': 'Беліз', 'en': 'Belize'}}, {'Code': 'BJ', 'Name': {'ru': 'Бенин', 'uk': 'Бенін', 'en': 'Benin'}}, {'Code': 'BM', 'Name': {'ru': 'Бермуды', 'uk': 'Бермуди', 'en': 'Bermuda'}}, {'Code': 'BT', 'Name': {'ru': 'Бутан', 'uk': 'Бутан', 'en': 'Bhutan'}}, {'Code': 'BO', 'Name': {'ru': 'Боливия', 'uk': 'Болівія', 'en': 'Bolivia, Plurinational State of'}}, {'Code': 'BQ', 'Name': {'ru': 'Бонайре, Синт-Эстатиус и Саба', 'uk': 'Бонайре, Синт-Естатіус і Саба', 'en': 'Bonaire, Sint Eustatius and Saba'}}, {'Code': 'BA', 'Name': {'ru': 'Босния и Герцеговина', 'uk': 'Боснія і Герцеговина', 'en': 'Bosnia and Herzegovina'}}, {'Code': 'BW', 'Name': {'ru': 'Ботсвана', 'uk': 'Ботсвана', 'en': 'Botswana'}}, {'Code': 'BV', 'Name': {'ru': 'Остров Буве', 'uk': 'Острів Буве', 'en': 'Bouvet Island'}}, {'Code': 'BR', 'Name': {'ru': 'Бразилия', 'uk': 'Бразилія', 'en': 'Brazil'}}, {'Code': 'IO', 'Name': {'ru': 'Британская территория в Индийском океане', 'uk': 'Британська територія в Індійскому океані', 'en': 'British Indian Ocean Territory'}}, {'Code': 'BN', 'Name': {'ru': 'Бруней Даруссалам', 'uk': 'Бруней Даруссалам', 'en': 'Brunei Darussalam'}}, {'Code': 'BG', 'Name': {'ru': 'Болгария', 'uk': 'Болгарія', 'en': 'Bulgaria'}}, {'Code': 'BF', 'Name': {'ru': 'Буркина-Фасо', 'uk': 'Буркина-Фасо', 'en': 'Burkina Faso'}}, {'Code': 'BI', 'Name': {'ru': 'Бурунди', 'uk': 'Бурунді', 'en': 'Burundi'}}, {'Code': 'KH', 'Name': {'ru': 'Камбоджа', 'uk': 'Камбоджа', 'en': 'Cambodia'}}, {'Code': 'CM', 'Name': {'ru': 'Камерун', 'uk': 'Камерун', 'en': 'Cameroon'}}, {'Code': 'CA', 'Name': {'ru': 'Канада', 'uk': 'Канада', 'en': 'Canada'}}, {'Code': 'CV', 'Name': {'ru': 'Кабо-Верде', 'uk': 'Кабо-Верде', 'en': 'Cape Verde'}}, {'Code': 'KY', 'Name': {'ru': 'Каймановы острова', 'uk': 'Кайманові острови', 'en': 'Cayman Islands'}}, {'Code': 'CF', 'Name': {'ru': 'Центральноафриканская Республика', 'uk': 'Центральноафриканська Республіка', 'en': 'Central African Republic'}}, {'Code': 'TD', 'Name': {'ru': 'Чад', 'uk': 'Чад', 'en': 'Chad'}}, {'Code': 'CL', 'Name': {'ru': 'Чили', 'uk': 'Чилі', 'en': 'Chile'}}, {'Code': 'CN', 'Name': {'ru': 'Китай', 'uk': 'Китай', 'en': 'China'}}, {'Code': 'CX', 'Name': {'ru': 'остров Рождества', 'uk': 'острів Різдва', 'en': 'Christmas Island'}}, {'Code': 'CC', 'Name': {'ru': 'Кокосовые острова', 'uk': 'Кокосові острови', 'en': 'Cocos (Keeling) Islands'}}, {'Code': 'CO', 'Name': {'ru': 'Колумбия', 'uk': 'Колумбія', 'en': 'Colombia'}}, {'Code': 'KM', 'Name': {'ru': 'Коморские Острова', 'uk': 'Коморскі Острови', 'en': 'Comoros'}}, {'Code': 'CG', 'Name': {'ru': 'Конго', 'uk': 'Конго', 'en': 'Congo'}}, {'Code': 'CD', 'Name': {'ru': 'Конго', 'uk': 'Конго', 'en': 'Congo, the Democratic Republic of the'}}, {'Code': 'CK', 'Name': {'ru': 'Острова Кука', 'uk': 'Острови Кука', 'en': 'Cook Islands'}}, {'Code': 'CR', 'Name': {'ru': 'Коста-Рика', 'uk': 'Коста-Ріка', 'en': 'Costa Rica'}}, {'Code': 'CI', 'Name': {'ru': 'Кот-д’Ивуар', 'uk': 'Кот-д’Івуар', 'en': "Côte d'Ivoire"}}, {'Code': 'HR', 'Name': {'ru': 'Хорватия', 'uk': 'Хорватія', 'en': 'Croatia'}}, {'Code': 'CU', 'Name': {'ru': 'Куба', 'uk': 'Куба', 'en': 'Cuba'}}, {'Code': 'CW', 'Name': {'ru': 'Кюрасао', 'uk': 'Кюрасао', 'en': 'Curaçao'}}, {'Code': 'CY', 'Name': {'ru': 'Кипр', 'uk': 'Кіпр', 'en': 'Cyprus'}}, {'Code': 'CZ', 'Name': {'ru': 'Чешская Республика', 'uk': 'Чеська Республіка', 'en': 'Czech Republic'}}, {'Code': 'DK', 'Name': {'ru': 'Дания', 'uk': 'Данія', 'en': 'Denmark'}}, {'Code': 'DJ', 'Name': {'ru': 'Джибути', 'uk': 'Джибуті', 'en': 'Djibouti'}}, {'Code': 'DM', 'Name': {'ru': 'Доминика', 'uk': 'Доміника', 'en': 'Dominica'}}, {'Code': 'DO', 'Name': {'ru': 'Доминиканская Республика', 'uk': 'Домініканська Республіка', 'en': 'Dominican Republic'}}, {'Code': 'EC', 'Name': {'ru': 'Эквадор', 'uk': 'Еквадор', 'en': 'Ecuador'}}, {'Code': 'EG', 'Name': {'ru': 'Египет', 'uk': 'Єгипет', 'en': 'Egypt'}}, {'Code': 'SV', 'Name': {'ru': 'Эль-Сальвадор', 'uk': 'Ель-Сальвадор', 'en': 'El Salvador'}}, {'Code': 'GQ', 'Name': {'ru': 'Экваториальная Гвинея', 'uk': 'Екваторіальна Гвінея', 'en': 'Equatorial Guinea'}}, {'Code': 'ER', 'Name': {'ru': 'Эритрея', 'uk': 'Еритрея', 'en': 'Eritrea'}}, {'Code': 'EE', 'Name': {'ru': 'Эстония', 'uk': 'Естонія', 'en': 'Estonia'}}, {'Code': 'ET', 'Name': {'ru': 'Эфиопия', 'uk': 'Ефіопія', 'en': 'Ethiopia'}}, {'Code': 'FK', 'Name': {'ru': 'Фолклендские острова', 'uk': 'Фолклендскі острови', 'en': 'Falkland Islands (Malvinas)'}}, {'Code': 'FO', 'Name': {'ru': 'Фарерские острова', 'uk': 'Фарерскі острови', 'en': 'Faroe Islands'}}, {'Code': 'FJ', 'Name': {'ru': 'Фиджи', 'uk': 'Фіджи', 'en': 'Fiji'}}, {'Code': 'FI', 'Name': {'ru': 'Финляндия', 'uk': 'Фінляндія', 'en': 'Finland'}}, {'Code': 'FR', 'Name': {'ru': 'Франция', 'uk': 'Франція', 'en': 'France'}}, {'Code': 'GF', 'Name': {'ru': 'Французская Гвиана', 'uk': 'Французька Гвіана', 'en': 'French Guiana'}}, {'Code': 'PF', 'Name': {'ru': 'Французская Полинезия', 'uk': 'Французька Полінезія', 'en': 'French Polynesia'}}, {'Code': 'TF', 'Name': {'ru': 'Французские Южные Территории', 'uk': 'Французькі Південні Території', 'en': 'French Southern Territories'}}, {'Code': 'GA', 'Name': {'ru': 'Габон', 'uk': 'Габон', 'en': 'Gabon'}}, {'Code': 'GM', 'Name': {'ru': 'Гамбия', 'uk': 'Гамбія', 'en': 'Gambia'}}, {'Code': 'GE', 'Name': {'ru': 'Грузия', 'uk': 'Грузія', 'en': 'Georgia'}}, {'Code': 'DE', 'Name': {'ru': 'Германия', 'uk': 'Германія', 'en': 'Germany'}}, {'Code': 'GH', 'Name': {'ru': 'Гана', 'uk': 'Гана', 'en': 'Ghana'}}, {'Code': 'GI', 'Name': {'ru': 'Гибралтар', 'uk': 'Гібралтар', 'en': 'Gibraltar'}}, {'Code': 'GR', 'Name': {'ru': 'Греция', 'uk': 'Греція', 'en': 'Greece'}}, {'Code': 'GL', 'Name': {'ru': 'Гренландия', 'uk': 'Гренландія', 'en': 'Greenland'}}, {'Code': 'GD', 'Name': {'ru': 'Гренада', 'uk': 'Гренада', 'en': 'Grenada'}}, {'Code': 'GP', 'Name': {'ru': 'Гваделупа', 'uk': 'Гваделупа', 'en': 'Guadeloupe'}}, {'Code': 'GU', 'Name': {'ru': 'Гуам', 'uk': 'Гуам', 'en': 'Guam'}}, {'Code': 'GT', 'Name': {'ru': 'Гватемала', 'uk': 'Гватемала', 'en': 'Guatemala'}}, {'Code': 'GG', 'Name': {'ru': 'Гернси', 'uk': 'Гернсі', 'en': 'Guernsey'}}, {'Code': 'GN', 'Name': {'ru': 'Гвинея', 'uk': 'Гвінея', 'en': 'Guinea'}}, {'Code': 'GW', 'Name': {'ru': 'Гвинея-Бисау', 'uk': 'Гвінея-Бісау', 'en': 'Guinea-Bissau'}}, {'Code': 'GY', 'Name': {'ru': 'Гайана', 'uk': 'Гайана', 'en': 'Guyana'}}, {'Code': 'HT', 'Name': {'ru': 'Гаити', 'uk': 'Гаїті', 'en': 'Haiti'}}, {'Code': 'HM', 'Name': {'ru': 'остров Херд и острова МакДональд', 'uk': 'острів Херд і острови МакДональд', 'en': 'Heard Island and McDonald Islands'}}, {'Code': 'VA', 'Name': {'ru': 'Святой Престол', 'uk': 'Святий Престол', 'en': 'Holy See (Vatican City State)'}}, {'Code': 'HN', 'Name': {'ru': 'Гондурас', 'uk': 'Гондурас', 'en': 'Honduras'}}, {'Code': 'HK', 'Name': {'ru': 'Гонконг', 'uk': 'Гонконг', 'en': 'Hong Kong'}}, {'Code': 'HU', 'Name': {'ru': 'Венгрия', 'uk': 'Угорщина', 'en': 'Hungary'}}, {'Code': 'IS', 'Name': {'ru': 'Исландия', 'uk': 'Ісландия', 'en': 'Iceland'}}, {'Code': 'IN', 'Name': {'ru': 'Индия', 'uk': 'Індия', 'en': 'India'}}, {'Code': 'ID', 'Name': {'ru': 'Индонезия', 'uk': 'Індонезія', 'en': 'Indonesia'}}, {'Code': 'IR', 'Name': {'ru': 'Иран', 'uk': 'Іран', 'en': 'Iran, Islamic Republic of'}}, {'Code': 'IQ', 'Name': {'ru': 'Ирак', 'uk': 'Ірак', 'en': 'Iraq'}}, {'Code': 'IE', 'Name': {'ru': 'Ирландия', 'uk': 'Ірландія', 'en': 'Ireland'}}, {'Code': 'IM', 'Name': {'ru': 'остров Мэн', 'uk': 'острів Мен', 'en': 'Isle of Man'}}, {'Code': 'IL', 'Name': {'ru': 'Израиль', 'uk': 'Ізраїль', 'en': 'Israel'}}, {'Code': 'IT', 'Name': {'ru': 'Италия', 'uk': 'Італія', 'en': 'Italy'}}, {'Code': 'JM', 'Name': {'ru': 'Ямайка', 'uk': 'Ямайка', 'en': 'Jamaica'}}, {'Code': 'JP', 'Name': {'ru': 'Япония', 'uk': 'Японія', 'en': 'Japan'}}, {'Code': 'JE', 'Name': {'ru': 'о. Джерси', 'uk': 'о. Джерсі', 'en': 'Jersey'}}, {'Code': 'JO', 'Name': {'ru': 'Иордания', 'uk': 'Йорданія', 'en': 'Jordan'}}, {'Code': 'KZ', 'Name': {'ru': 'Казахстан', 'uk': 'Казахстан', 'en': 'Kazakhstan'}}, {'Code': 'KE', 'Name': {'ru': 'Кения', 'uk': 'Кенія', 'en': 'Kenya'}}, {'Code': 'KI', 'Name': {'ru': 'Кирибати', 'uk': 'Кирібаті', 'en': 'Kiribati'}}, {'Code': 'KP', 'Name': {'ru': 'КНДР', 'uk': 'КНДР', 'en': "Korea, Democratic People's Republic of"}}, {'Code': 'KR', 'Name': {'ru': 'Республика Корея', 'uk': 'Республіка Корея', 'en': 'Korea, Republic of'}}, {'Code': 'KW', 'Name': {'ru': 'Кувейт', 'uk': 'Кувейт', 'en': 'Kuwait'}}, {'Code': 'KG', 'Name': {'ru': 'Киргизстан', 'uk': 'Киргизстан', 'en': 'Kyrgyzstan'}}, {'Code': 'LA', 'Name': {'ru': 'Лаосская Народно-Демократическая Республика', 'uk': 'Лаосская Народно-Демократическая Республика', 'en': "Lao People's Democratic Republic"}}, {'Code': 'LV', 'Name': {'ru': 'Латвия', 'uk': 'Латвия', 'en': 'Latvia'}}, {'Code': 'LB', 'Name': {'ru': 'Ливан', 'uk': 'Ливан', 'en': 'Lebanon'}}, {'Code': 'LS', 'Name': {'ru': 'Лесото', 'uk': 'Лесото', 'en': 'Lesotho'}}, {'Code': 'LR', 'Name': {'ru': 'Либерия', 'uk': 'Либерия', 'en': 'Liberia'}}, {'Code': 'LY', 'Name': {'ru': 'Ливия', 'uk': 'Ливия', 'en': 'Libya'}}, {'Code': 'LI', 'Name': {'ru': 'Лихтенштейн', 'uk': 'Лихтенштейн', 'en': 'Liechtenstein'}}, {'Code': 'LT', 'Name': {'ru': 'Литва', 'uk': 'Литва', 'en': 'Lithuania'}}, {'Code': 'LU', 'Name': {'ru': 'Люксембург', 'uk': 'Люксембург', 'en': 'Luxembourg'}}, {'Code': 'MO', 'Name': {'ru': 'Макао', 'uk': 'Макао', 'en': 'Macao'}}, {'Code': 'MK', 'Name': {'ru': 'Македония', 'uk': 'Македония', 'en': 'Macedonia, the Former Yugoslav Republic of'}}, {'Code': 'MG', 'Name': {'ru': 'Мадагаскар', 'uk': 'Мадагаскар', 'en': 'Madagascar'}}, {'Code': 'MW', 'Name': {'ru': 'Малави', 'uk': 'Малави', 'en': 'Malawi'}}, {'Code': 'MY', 'Name': {'ru': 'Малайзия', 'uk': 'Малайзия', 'en': 'Malaysia'}}, {'Code': 'MV', 'Name': {'ru': 'Мальдивы', 'uk': 'Мальдивы', 'en': 'Maldives'}}, {'Code': 'ML', 'Name': {'ru': 'Мали', 'uk': 'Мали', 'en': 'Mali'}}, {'Code': 'MT', 'Name': {'ru': 'Мальта', 'uk': 'Мальта', 'en': 'Malta'}}, {'Code': 'MH', 'Name': {'ru': 'Маршалловы острова', 'uk': 'Маршалловы острова', 'en': 'Marshall Islands'}}, {'Code': 'MQ', 'Name': {'ru': 'Мартиника', 'uk': 'Мартиника', 'en': 'Martinique'}}, {'Code': 'MR', 'Name': {'ru': 'Мавритания', 'uk': 'Мавритания', 'en': 'Mauritania'}}, {'Code': 'MU', 'Name': {'ru': 'Маврикий', 'uk': 'Маврикий', 'en': 'Mauritius'}}, {'Code': 'YT', 'Name': {'ru': 'Майотта', 'uk': 'Майотта', 'en': 'Mayotte'}}, {'Code': 'MX', 'Name': {'ru': 'Мексика', 'uk': 'Мексика', 'en': 'Mexico'}}, {'Code': 'FM', 'Name': {'ru': 'Микронезия', 'uk': 'Микронезия', 'en': 'Micronesia, Federated States of'}}, {'Code': 'MD', 'Name': {'ru': 'Молдова', 'uk': 'Молдова', 'en': 'Moldova, Republic of'}}, {'Code': 'MC', 'Name': {'ru': 'Монако', 'uk': 'Монако', 'en': 'Monaco'}}, {'Code': 'MN', 'Name': {'ru': 'Монголия', 'uk': 'Монголия', 'en': 'Mongolia'}}, {'Code': 'ME', 'Name': {'ru': 'Черногория', 'uk': 'Черногория', 'en': 'Montenegro'}}, {'Code': 'MS', 'Name': {'ru': 'о. Монтсеррат', 'uk': 'о. Монтсеррат', 'en': 'Montserrat'}}, {'Code': 'MA', 'Name': {'ru': 'Марокко', 'uk': 'Марокко', 'en': 'Morocco'}}, {'Code': 'MZ', 'Name': {'ru': 'Мозамбик', 'uk': 'Мозамбик', 'en': 'Mozambique'}}, {'Code': 'MM', 'Name': {'ru': 'Мьянма', 'uk': 'Мьянма', 'en': 'Myanmar'}}, {'Code': 'NA', 'Name': {'ru': 'Намибия', 'uk': 'Намибия', 'en': 'Namibia'}}, {'Code': 'NR', 'Name': {'ru': 'Науру', 'uk': 'Науру', 'en': 'Nauru'}}, {'Code': 'NP', 'Name': {'ru': 'Непал', 'uk': 'Непал', 'en': 'Nepal'}}, {'Code': 'NL', 'Name': {'ru': 'Нидерланды', 'uk': 'Нидерланды', 'en': 'Netherlands'}}, {'Code': 'NC', 'Name': {'ru': 'Новая Каледония', 'uk': 'Новая Каледония', 'en': 'New Caledonia'}}, {'Code': 'NZ', 'Name': {'ru': 'Новая Зеландия', 'uk': 'Новая Зеландия', 'en': 'New Zealand'}}, {'Code': 'NI', 'Name': {'ru': 'Никарагуа', 'uk': 'Никарагуа', 'en': 'Nicaragua'}}, {'Code': 'NE', 'Name': {'ru': 'Нигер', 'uk': 'Нигер', 'en': 'Niger'}}, {'Code': 'NG', 'Name': {'ru': 'Нигерия', 'uk': 'Нигерия', 'en': 'Nigeria'}}, {'Code': 'NU', 'Name': {'ru': 'Ниуэ', 'uk': 'Ниуэ', 'en': 'Niue'}}, {'Code': 'NF', 'Name': {'ru': 'о. Норфолк', 'uk': 'о. Норфолк', 'en': 'Norfolk Island'}}, {'Code': 'MP', 'Name': {'ru': 'Северные Марианские острова', 'uk': 'Северные Марианские острова', 'en': 'Northern Mariana Islands'}}, {'Code': 'NO', 'Name': {'ru': 'Норвегия', 'uk': 'Норвегия', 'en': 'Norway'}}, {'Code': 'OM', 'Name': {'ru': 'Оман', 'uk': 'Оман', 'en': 'Oman'}}, {'Code': 'PK', 'Name': {'ru': 'Пакистан', 'uk': 'Пакистан', 'en': 'Pakistan'}}, {'Code': 'PW', 'Name': {'ru': 'Палау', 'uk': 'Палау', 'en': 'Palau'}}, {'Code': 'PS', 'Name': {'ru': 'Палестина', 'uk': 'Палестина', 'en': 'Palestine, State of'}}, {'Code': 'PA', 'Name': {'ru': 'Панама', 'uk': 'Панама', 'en': 'Panama'}}, {'Code': 'PG', 'Name': {'ru': 'Папуа-Новая Гвинея', 'uk': 'Папуа-Новая Гвинея', 'en': 'Papua New Guinea'}}, {'Code': 'PY', 'Name': {'ru': 'Парагвай', 'uk': 'Парагвай', 'en': 'Paraguay'}}, {'Code': 'PE', 'Name': {'ru': 'Перу', 'uk': 'Перу', 'en': 'Peru'}}, {'Code': 'PH', 'Name': {'ru': 'Филиппины', 'uk': 'Филиппины', 'en': 'Philippines'}}, {'Code': 'PN', 'Name': {'ru': 'Питкэрн', 'uk': 'Питкэрн', 'en': 'Pitcairn'}}, {'Code': 'PL', 'Name': {'ru': 'Польша', 'uk': 'Польща', 'en': 'Poland'}}, {'Code': 'PT', 'Name': {'ru': 'Португалия', 'uk': 'Португалія', 'en': 'Portugal'}}, {'Code': 'PR', 'Name': {'ru': 'Пуэрто-Рико', 'uk': 'Пуэрто-Рико', 'en': 'Puerto Rico'}}, {'Code': 'QA', 'Name': {'ru': 'Катар', 'uk': 'Катар', 'en': 'Qatar'}}, {'Code': 'RE', 'Name': {'ru': 'о. Реюньон ', 'uk': 'о. Реюньон ', 'en': 'Réunion'}}, {'Code': 'RO', 'Name': {'ru': 'Румыния', 'uk': 'Румыния', 'en': 'Romania'}}, {'Code': 'RU', 'Name': {'ru': 'Российская Федерация', 'uk': 'Российская Федерация', 'en': 'Russian Federation'}}, {'Code': 'RW', 'Name': {'ru': 'Руанда', 'uk': 'Руанда', 'en': 'Rwanda'}}, {'Code': 'BL', 'Name': {'ru': 'Сен-Бартелеми', 'uk': 'Сен-Бартелеми', 'en': 'Saint Barthélemy'}}, {'Code': 'SH', 'Name': {'ru': 'о. Святой Елены', 'uk': 'о. Святой Елены', 'en': 'Saint Helena, Ascension and Tristan da Cunha'}}, {'Code': 'KN', 'Name': {'ru': 'Сент-Китс и Невис', 'uk': 'Сент-Китс и Невис', 'en': 'Saint Kitts and Nevis'}}, {'Code': 'LC', 'Name': {'ru': 'Сент-Люсия', 'uk': 'Сент-Люсия', 'en': 'Saint Lucia'}}, {'Code': 'MF', 'Name': {'ru': 'Сен-Мартен', 'uk': 'Сен-Мартен', 'en': 'Saint Martin (French part)'}}, {'Code': 'PM', 'Name': {'ru': 'Сен-Пьер и Микелон', 'uk': 'Сен-Пьер и Микелон', 'en': 'Saint Pierre and Miquelon'}}, {'Code': 'VC', 'Name': {'ru': 'Сент-Винсент и Гренадины', 'uk': 'Сент-Винсент и Гренадины', 'en': 'Saint Vincent and the Grenadines'}}, {'Code': 'WS', 'Name': {'ru': 'Самоа', 'uk': 'Самоа', 'en': 'Samoa'}}, {'Code': 'SM', 'Name': {'ru': 'Сан Марино', 'uk': 'San Marino', 'en': 'San Marino'}}, {'Code': 'ST', 'Name': {'ru': 'Сан-Томе и Принсипи', 'uk': 'Сан-Томе и Принсипи', 'en': 'Sao Tome and Principe'}}, {'Code': 'SA', 'Name': {'ru': 'Саудовская Аравия', 'uk': 'Саудовская Аравия', 'en': 'Saudi Arabia'}}, {'Code': 'SN', 'Name': {'ru': 'Сенегал', 'uk': 'Сенегал', 'en': 'Senegal'}}, {'Code': 'RS', 'Name': {'ru': 'Сербия', 'uk': 'Сербия', 'en': 'Serbia'}}, {'Code': 'SC', 'Name': {'ru': 'Сейшеллы', 'uk': 'Сейшеллы', 'en': 'Seychelles'}}, {'Code': 'SL', 'Name': {'ru': '\tСьерра-Леоне', 'uk': '\tСьерра-Леоне', 'en': 'Sierra Leone'}}, {'Code': 'SG', 'Name': {'ru': 'Сингапур', 'uk': 'Сингапур', 'en': 'Singapore'}}, {'Code': 'SX', 'Name': {'ru': 'Синт-Мартен', 'uk': 'Синт-Мартен', 'en': 'Sint Maarten (Dutch part)'}}, {'Code': 'SK', 'Name': {'ru': 'Словакия', 'uk': 'Словакия', 'en': 'Slovakia'}}, {'Code': 'SI', 'Name': {'ru': 'Словения', 'uk': 'Словенія', 'en': 'Slovenia'}}, {'Code': 'SB', 'Name': {'ru': 'Соломоновы Острова', 'uk': 'Соломоновы Острова', 'en': 'Solomon Islands'}}, {'Code': 'SO', 'Name': {'ru': 'Сомали', 'uk': 'Сомали', 'en': 'Somalia'}}, {'Code': 'ZA', 'Name': {'ru': 'ЮАР', 'uk': 'ЮАР', 'en': 'South Africa'}}, {'Code': 'GS', 'Name': {'ru': 'Южная Георгия и Южные Сандвичевы острова', 'uk': 'Южная Георгия и Южные Сандвичевы острова', 'en': 'South Georgia and the South Sandwich Islands'}}, {'Code': 'SS', 'Name': {'ru': 'Южный Судан', 'uk': 'Южный Судан', 'en': 'South Sudan'}}, {'Code': 'ES', 'Name': {'ru': 'Испания', 'uk': 'Испания', 'en': 'Spain'}}, {'Code': 'LK', 'Name': {'ru': 'Шри-Ланка', 'uk': 'Шри-Ланка', 'en': 'Sri Lanka'}}, {'Code': 'SD', 'Name': {'ru': 'Судан', 'uk': 'Судан', 'en': 'Sudan'}}, {'Code': 'SR', 'Name': {'ru': 'Суринам', 'uk': 'Суринам', 'en': 'Suriname'}}, {'Code': 'SJ', 'Name': {'ru': 'Шпицберген и Ян-Майен', 'uk': 'Шпицберген и Ян-Майен', 'en': 'Svalbard and Jan Mayen'}}, {'Code': 'SZ', 'Name': {'ru': 'Свазиленд', 'uk': 'Свазиленд', 'en': 'Swaziland'}}, {'Code': 'SE', 'Name': {'ru': 'Швеция', 'uk': 'Швеция', 'en': 'Sweden'}}, {'Code': 'CH', 'Name': {'ru': 'Швейцария', 'uk': 'Швейцария', 'en': 'Switzerland'}}, {'Code': 'SY', 'Name': {'ru': 'Сирия', 'uk': 'Сирия', 'en': 'Syrian Arab Republic'}}, {'Code': 'TW', 'Name': {'ru': 'Тайвань', 'uk': 'Тайвань', 'en': 'Taiwan, Province of China'}}, {'Code': 'TJ', 'Name': {'ru': 'Таджикистан', 'uk': 'Таджикистан', 'en': 'Tajikistan'}}, {'Code': 'TZ', 'Name': {'ru': 'Танзания', 'uk': 'Танзания', 'en': 'Tanzania, United Republic of'}}, {'Code': 'TH', 'Name': {'ru': 'Таиланд', 'uk': 'Таиланд', 'en': 'Thailand'}}, {'Code': 'TL', 'Name': {'ru': 'Восточный Тимор', 'uk': 'Восточный Тимор', 'en': 'Timor-Leste'}}, {'Code': 'TG', 'Name': {'ru': 'Того', 'uk': 'Того', 'en': 'Togo'}}, {'Code': 'TK', 'Name': {'ru': 'Токелау', 'uk': 'Токелау', 'en': 'Tokelau'}}, {'Code': 'TO', 'Name': {'ru': 'Тонга', 'uk': 'Тонга', 'en': 'Tonga'}}, {'Code': 'TT', 'Name': {'ru': 'Тринидад и Тобаго', 'uk': 'Тринидад и Тобаго', 'en': 'Trinidad and Tobago'}}, {'Code': 'TN', 'Name': {'ru': 'Тунис', 'uk': 'Тунис', 'en': 'Tunisia'}}, {'Code': 'TR', 'Name': {'ru': 'Турция', 'uk': 'Туреччина', 'en': 'Turkey'}}, {'Code': 'TM', 'Name': {'ru': 'Туркменистан', 'uk': 'Туркменістан', 'en': 'Turkmenistan'}}, {'Code': 'TC', 'Name': {'ru': 'Теркс и Кайкос', 'uk': 'Теркс і Кайкос', 'en': 'Turks and Caicos Islands'}}, {'Code': 'TV', 'Name': {'ru': 'Тувалу', 'uk': 'Тувалу', 'en': 'Tuvalu'}}, {'Code': 'UG', 'Name': {'ru': 'Уганда', 'uk': 'Уганда', 'en': 'Uganda'}}, {'Code': 'UA', 'Name': {'ru': 'Украина', 'uk': 'Україна', 'en': 'Ukraine'}}, {'Code': 'AE', 'Name': {'ru': 'Объединенные Арабские Эмираты', 'uk': "Об'єднані Арабскі Емірати", 'en': 'United Arab Emirates'}}, {'Code': 'GB', 'Name': {'ru': 'Совединенное Королевство', 'uk': 'Сполучене Королівство', 'en': 'United Kingdom'}}, {'Code': 'US', 'Name': {'ru': 'США', 'uk': 'США', 'en': 'United States'}}, {'Code': 'UM', 'Name': {'ru': 'Малые Удаленные Острова США', 'uk': 'Малі Віддалені Острови США', 'en': 'United States Minor Outlying Islands'}}, {'Code': 'UY', 'Name': {'ru': 'Уругвай', 'uk': 'Уругвай', 'en': 'Uruguay'}}, {'Code': 'UZ', 'Name': {'ru': 'Узбекистан', 'uk': 'Узбекистан', 'en': 'Uzbekistan'}}, {'Code': 'VU', 'Name': {'ru': 'Вануату', 'uk': 'Вануату', 'en': 'Vanuatu'}}, {'Code': 'VE', 'Name': {'ru': 'Венесуэла', 'uk': 'Венесуела', 'en': 'Venezuela, Bolivarian Republic of'}}, {'Code': 'VN', 'Name': {'ru': 'Вьетнам', 'uk': "В'єтнам", 'en': 'Viet Nam'}}, {'Code': 'VG', 'Name': {'ru': 'Виргинские острова [Великобритания]', 'uk': 'Віргінскі острови [Великобританія]', 'en': 'Virgin Islands, British'}}, {'Code': 'VI', 'Name': {'ru': 'Виргинские острова [США]', 'uk': 'Віргінскі острови [США]', 'en': 'Virgin Islands, U.S.'}}, {'Code': 'WF', 'Name': {'ru': 'о-ва Уоллис и Футуна', 'uk': 'о-ви Уолліс і Футуна', 'en': 'Wallis and Futuna'}}, {'Code': 'EH', 'Name': {'ru': 'Западная Сахара', 'uk': 'Західна Сахара', 'en': 'Western Sahara'}}, {'Code': 'YE', 'Name': {'ru': 'Йемен', 'uk': 'Йемен', 'en': 'Yemen'}}, {'Code': 'ZM', 'Name': {'ru': 'Замбия', 'uk': 'Замбія', 'en': 'Zambia'}}, {'Code': 'ZW', 'Name': {'ru': 'Зимбабве', 'uk': 'Зімбабве', 'en': 'Zimbabwe'}}]


SITE_URL = 'https://fellowtraveler.club'
BASIC_TRAVELER = 'Teddy'
ALL_TRAVELERS = ['Teddy']

def valid_url_extension(url, extension_list=VALID_IMAGE_EXTENSIONS):
    '''
    Validating image extension
    A simple method to make sure the URL the user has supplied has
    an image-like file at the tail of the path
    '''
    return any([url.endswith(e) for e in extension_list])


def valid_url_mimetype(url, mimetype_list=VALID_IMAGE_MIMETYPES):
    '''
    Validating image mimetype
    http://stackoverflow.com/a/10543969/396300
    '''
    mimetype, encoding = mimetypes.guess_type(url)
    if mimetype:
        return any([mimetype.startswith(m) for m in mimetype_list])
    else:
        return False


def image_exists(url):
    '''
    Validating that the image exists on the server
    '''
    try:
        r = requests.get(url)
    except:
        return False
    return r.status_code == 200


def photo_check_save(photo_file, OURTRAVELER):
    '''
    Check image validity using valid_url_extension() and valid_url_mimetype() and return new file name or flash an error
    '''
    photo_filename = secure_filename(photo_file.filename)
    if valid_url_extension(photo_filename) and valid_url_mimetype(photo_filename):
        file_name_wo_extension = 'fellowtravelerclub-{}'.format(OURTRAVELER)
        file_extension = os.path.splitext(photo_filename)[1]
        current_datetime = datetime.datetime.now().strftime("%d%m%y%H%M%S")
        random_int = randint(100, 999)
        path4db = file_name_wo_extension + '-' + current_datetime + str(random_int) + file_extension
        return path4db
    else:
        flash(lazy_gettext('File {} has invalid image extension (not ".jpg", ".jpeg", ".png", ".gif" or ".bmp") or invalid image format').format(photo_filename),
            'addlocation')
        return 'error'


def get_location_history(traveller, PHOTO_DIR):
    '''
    Return locations history for a given traveller (will be substituted with Twitter's timeline)
    '''
    client = MongoClient()
    db = client.TeddyGo
    teddys_locations = db[traveller].find().sort([('_id', -1)])

    # Prepare a list of info blocks about traveller's locations and data to create a map
    locations_history = []
    mymarkers = []
    start_lat = None
    start_long = None
    marker_number = db[traveller].find().count()
    for location in teddys_locations:
        author = location['author']
        comment = location['comment']
        photos = location['photos']

        location_data = {
            'location_number': marker_number,
            'author': author,
            'location': location['formatted_address'],
            'time': '{} {}'.format(location['_id'].generation_time.date(), location['_id'].generation_time.time()),
            'comment': comment,
            'photos': photos
        }

        locations_history.append(location_data)

        if start_lat == None:
            start_lat = location['latitude']
            start_long = location['longitude']
        infobox = '{}<br>'.format(location_data['time'])
        if len(photos) > 0:
            infobox += '<img src="{}/{}/{}" style="max-height: 70px; max-width:120px"/>'.format(PHOTO_DIR, traveller, photos[0])
        infobox += '<br>'
        infobox += gettext('By <b>{}</b>').format(author)
        if comment != '':
            infobox += '<br>'
            infobox += '<i>{}</i>'.format(comment)

        mymarkers.append(
            {
                'icon': 'http://chart.apis.google.com/chart?chst=d_map_pin_letter&chld={}|AFC846|304300'.format(marker_number),
                'lat': location['latitude'],
                'lng': location['longitude'],
                'infobox': infobox
            }
        )
        marker_number -= 1
    return {'locations_history': locations_history, 'start_lat': start_lat, 'start_long': start_long, 'mymarkers': mymarkers}


def summarize_journey(traveller):
    '''
        For a given traveller (for eg., "Teddy") function retrieves documents from our mongoDB (TeddyGo >> Teddy)
        and summarizes:
        1) place of origin;
        2) journey start date/time;
        3) quantity of places traveller was "checked in";
        4) list of locations coordinates to (later) calculate approximate distance between locations;
        5) quantity of countries visited;
        6) list of countries visited
        Data are saved to document TeddyGo >> travellers >> <Traveller>
    '''
    client = MongoClient()
    db = client.TeddyGo
    locations = db[traveller].find()

    origin = locations[0]['formatted_address']  # 1
    start_date = '{} {}'.format(locations[0]['_id'].generation_time.date(), locations[0]['_id'].generation_time.time()) # 2
    start_date_service = locations[0]['_id'].generation_time
    total_locations = 0 #3
    locations_lat_long = []  # 4
    total_countries = 0 #5
    countries_visited = [] #6

    for location in locations:
        total_locations += 1

        contry_name = location['country']
        if contry_name not in countries_visited:
            total_countries += 1
            countries_visited.append(contry_name)

        lat = location['latitude']
        lng = location['longitude']
        locations_lat_long.append({'latitude': lat, 'longitude': lng})

        datatoupdate = {
            'origin': origin,
            'start_date': start_date,
            'start_date_service': start_date_service,
            'total_locations': total_locations,
            'locations_lat_long': locations_lat_long,
            'total_countries': total_countries,
            'countries_visited': countries_visited
        }

    # Update total distance and distance from home
    new_distance_from_home = distance_from_home(traveller)
    if new_distance_from_home:
        datatoupdate['distance_from_home'] = new_distance_from_home
    new_total_distance = last_segment_distance_append(traveller)
    if new_total_distance:
        datatoupdate['total_distance'] = new_total_distance

    try:
        db.travellers.update_one({'name': traveller}, {'$set': datatoupdate})
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

    return {'status': 'success', 'message': datatoupdate}


def get_journey_summary(traveller):
    '''
    Composes journey summary for a given traveller, returns 6 values:
    - total_locations
    - total_countries
    - journey_duration
    - total_distance
    - distance_from_home
    - [countries_visited]
    '''
    try:
        client = MongoClient()
        db = client.TeddyGo

        # Message: I've checked in ... places in ... country[ies] (country1 [, country2 etc]) and have been traveling for ... days so far
        traveller_summary = db.travellers.find_one({'name': traveller})
        if traveller_summary:
            total_locations = traveller_summary['total_locations']
            total_countries = traveller_summary['total_countries']
            countries_visited = traveller_summary['countries_visited']
            countries = ', '.join(countries_visited)
            journey_duration = time_passed(traveller)
            total_distance = round(traveller_summary['total_distance'] / 1000, 1)
            distance_from_home = round(traveller_summary['distance_from_home'] / 1000, 1)
            return {'total_locations': total_locations, 'total_countries': total_countries, 'journey_duration': journey_duration, 'total_distance': total_distance, 'distance_from_home': distance_from_home, 'countries_visited': countries_visited}
        else:
            return {'total_locations': 0, 'total_countries': 0, 'total_distance': 0, 'distance_from_home': 0, 'countries_visited': []}
    except Exception as e:
        print('get_journey_summary() exception: {}'.format(e))
        return False


def time_passed(traveller):
    '''
        Function calculates time elapsed from origin date/time for a given traveller
    '''
    client = MongoClient()
    db = client.TeddyGo
    traveller_resume = db.travellers.find_one({'name': traveller})
    start_date_service = traveller_resume['start_date_service']
    current_datetime = datetime.datetime.now()
    difference = (current_datetime - start_date_service).days
    return difference


def get_distance(origin, destination):
    '''
        Uusing Distance Matrix API calculates and returns approximate distance (m) between origin and destination
        (lists of latitude/longitude)
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        query = 'https://maps.googleapis.com/maps/api/distancematrix/json?units=metric&origins={},{}&destinations={},{}&key={}'.format(
            origin[0], origin[1], destination[0], destination[1], GOOGLE_MAPS_API_KEY)
        r = requests.get(query).json()
        distance = r.get('rows', 0)[0].get('elements', 0)[0].get('distance', 0).get('value', 0)
        return distance
    except Exception as e:
        print('get_distance() exception: {}'.format(e))
        return False


def journey_distance_recalculate(traveller):
    '''
        Calculates using Distance Matrix API approximate distance (km) between all locations visited by traveller
        https://developers.google.com/maps/documentation/distance-matrix/intro
        Function may be used in case some location is deleted from DB
        Otherwise after adding every location function journey_distance() calculates distance between the last
        2 locations and updates total distance value stored in DB (TeddyGo >> travellers >> <Traveller> document >>
        'total_distance' field
    '''
    try:
        client = MongoClient()
        db = client.TeddyGo
        locations = db[traveller].find()

        locations_lat_lng = []
        lat_lng_pair = []
        journey_distance = 0 # meters, integer

        for location in locations:
            lat_lng_pair.append(location['latitude'])
            lat_lng_pair.append(location['longitude'])
            locations_lat_lng.append(lat_lng_pair)
            lat_lng_pair = []

        for x in range(1, len(locations_lat_lng)):
            origin = locations_lat_lng[x-1]
            destination = locations_lat_lng[x]
            segment_distance = get_distance(origin, destination)
            if not segment_distance:
                segment_distance = 0

            journey_distance += segment_distance

        db.travellers.update_one({'name': traveller}, {'$set': {'total_distance': journey_distance}})
        return True
    except Exception as e:
        print('journey_distance_recalculate() exception: {}'.format(e))
        return False


def distance_from_home(traveller):
    '''
        Using Distance Matrix API calculates and returns approximate distance (meters) between the 1st and the last locations
        (this distance may be less than the sum of distances between all locations if traveller is 'returning home' for eg.)
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        distance_from_home = 0

        client = MongoClient()
        db = client.TeddyGo
        if db[traveller].find().count() >= 2:
            origin_location = db[traveller].find().limit(1)[0]
            last_location = db[traveller].find().limit(1).sort([('_id', -1)])[0]

            origin = [origin_location['latitude'], origin_location['longitude']]
            destination = [last_location['latitude'], last_location['longitude']]

            distance_from_home = get_distance(origin, destination)
            if not distance_from_home:
                distance_from_home = 0
        return distance_from_home
    except Exception as e:
        print('distance_from_home() exception: {}'.format(e))
        return False


def last_segment_distance_append(traveller):
    '''
        Using Distance Matrix API calculates approximate distance (meters) between the last 2 locations and
        adds it to the value of 'total_distance' field in db TeddyGo >> travellers >> <Traveller> document
        The function is used after adding every location
        https://developers.google.com/maps/documentation/distance-matrix/intro
    '''
    try:
        new_distance = 0

        client = MongoClient()
        db = client.TeddyGo
        if db[traveller].find().count() >= 2:
            locations = db[traveller].find().sort([('_id', -1)]).limit(2)
            curr_location = locations[0]
            prev_location = locations[1]

            # Total distance before current location was added ('total_distance' field in <Traveller> doc)
            last_distance = db.travellers.find_one({'name': traveller})['total_distance']

            origin = [prev_location['latitude'], prev_location['longitude']]
            destination = [curr_location['latitude'], curr_location['longitude']]

            last_segment_distance = get_distance(origin, destination)

            if not last_segment_distance:
                last_segment_distance = 0

            new_distance = last_distance + last_segment_distance
        return new_distance
    except Exception as e:
        print('last_segment_distance_append() exception: {}'.format(e))
        return False


def code_regenerate(traveller):
    '''
        After adding a new location secret code is being regenerated so that if user1 passes the toy
        to user2, user1 should not be able to add new locations or share secret code
        New code is saved to traveller's summary document in DB (TeddyGo >> travellers >> <TravellerName>), secret_code
    '''
    new_code = ''
    for x in range(4):
        new_code += str(randint(0,9))
    try:
        client = MongoClient()
        db = client.TeddyGo
        db.travellers.update_one({'name': traveller}, {'$set': {'secret_code': sha256_crypt.encrypt(new_code)}})
    except Exception as e:
        print('code_regenerate() exception when updating secret code in DB: {}'.format(e))
        return False

    # Logging
    print()
    print('New secret code for {}: {}'.format(traveller, new_code))
    return new_code


def get_locale():
    user_language = request.cookies.get('UserPreferredLanguage')
    if user_language != None:
        return user_language
    else:
        return request.accept_languages.best_match(LANGUAGES.keys())


def get_traveler():
    '''
        Retrieves traveler watched by user from session
        By default returns BASIC_TRAVELER
    '''
    OURTRAVELER = session.get('which_traveler', BASIC_TRAVELER)
    if OURTRAVELER not in ALL_TRAVELERS:
        OURTRAVELER = BASIC_TRAVELER
    return OURTRAVELER


def translate_countries(countries_list, language):
    '''
        Function gets a list of countries and language code and returns
        these countries in appropriate language
    '''
    countries_translated = []
    for country_code in countries_list:
        for country in COUNTRIES_CODES_NAMES: # {'Code': 'AF', 'Name': {'ru': 'Афганистан', 'uk': 'Афганістан', 'en': 'Afghanistan'}}
            if country_code == country['Code']:
                country_translated = country['Name'][language]
                countries_translated.append(country_translated)
    return countries_translated