from telebot import types

OURTRAVELLER = 'Teddy'

# All possible buttons: Yes, No, Next, FAQ, <Traveler>'s story, You got traveler

intro_menu = types.InlineKeyboardMarkup()
intro_menu_mystory = types.InlineKeyboardButton("{}\'s story".format(OURTRAVELLER), callback_data="Tell your story")
intro_menu_help = types.InlineKeyboardButton("Help", callback_data="FAQ")
intro_menu_gotteddy = types.InlineKeyboardButton("You got {}?".format(OURTRAVELLER), callback_data="You got fellowtraveler")
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