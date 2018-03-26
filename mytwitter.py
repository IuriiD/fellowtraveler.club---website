import twitter

twitter_api = twitter.Api(consumer_key='zcRRXyvzQ2gjwxZNOFRG3Iah9',
                  consumer_secret='FUZ7HTV0VPDGiZx1FVQFwDUOYnV1SeRXlYjGA4RyKCaNAe49kJ',
                  access_token_key='230100570-HLZfO7fdHmmXJ0RGWjTTmirPwP4z6LbNG8jFbzG5',
                  access_token_secret='9y2kkAACCNNiSAwqnUale1jjMLudUYmwvYb3WJpRY0g6a')

author = 'Tim'
comment = 'Local upload'
mylatitude = 47.497912
mylongitude = 19.04023499999994
formatted_address = 'Будапешт, Венгрия'
photos = ['teddy.png']
newstatus = 'Teddy with {} in {}'.format(author, formatted_address)
if comment != '':
    newstatus += '. {} wrote: {}'.format(author, comment)

status = twitter_api.PostUpdate(status=newstatus, media=photos, latitude=mylatitude, longitude=mylongitude, display_coordinates=True)
print(status.text)