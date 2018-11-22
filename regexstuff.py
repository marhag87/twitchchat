import re


text = 'monkaSHAKE'
emotes = ['monkaS', 'monkaSHAKE']

for emote in emotes:
    print(re.sub(rf'\b{emote}\b', 'replaced', text))
