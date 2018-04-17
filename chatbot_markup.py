from telebot import types

intro_menu = types.InlineKeyboardMarkup()
intro_menu_mystory = types.InlineKeyboardButton("Teddy\'s story", callback_data="Teddy\'s story")
intro_menu_help = types.InlineKeyboardButton("Help", callback_data="FAQ")
intro_menu_gotteddy = types.InlineKeyboardButton("You got Teddy?", callback_data="You got Teddy")
intro_menu.row(intro_menu_mystory, intro_menu_help, intro_menu_gotteddy)

yes_no_menu = types.InlineKeyboardMarkup()
yes_no_menu_yes = types.InlineKeyboardButton("Yes", callback_data="Yes")
yes_no_menu_no = types.InlineKeyboardButton("No, thanks", callback_data="No")
yes_no_menu.row(yes_no_menu_yes, yes_no_menu_no)

yes_no_help_menu = types.InlineKeyboardMarkup()
yes_no_help_menu_yes = types.InlineKeyboardButton("Yes", callback_data="Yes")
yes_no_help_menu_no = types.InlineKeyboardButton("No, thanks", callback_data="No")
yes_no_help_menu_help = types.InlineKeyboardButton("Help", callback_data="FAQ")
yes_no_help_menu.row(yes_no_menu_yes, yes_no_menu_no, yes_no_help_menu_help)

next_or_help_menu = types.InlineKeyboardMarkup()
next_or_help_next = types.InlineKeyboardButton("Next", callback_data="Next")
next_or_help_help = types.InlineKeyboardButton("Help", callback_data="FAQ")
next_or_help_menu.row(next_or_help_next, next_or_help_help)