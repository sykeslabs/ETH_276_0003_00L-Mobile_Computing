import random


TRAINING_SENTENCES = [
    'mix flour and sugar for a soft cake',
    'mix flour and sugar for sweet cookies',
    'add butter and milk to the cake bowl',
    'add butter and milk to the cookie bowl',
    'stir the cake batter until it is smooth',
    'stir the cookie dough until it is soft',
    'bake the cake until the top is golden',
    'bake the cookies until the edges are golden',
    'cool the cake before adding sweet cream',
    'cool the cookies before adding sugar dust',
    'slice the cake and serve it warm',
    'share the cookies and serve them warm',
    'vanilla makes the cake smell sweet',
    'vanilla makes the cookies smell sweet',
    'chocolate chips make the cookies rich',
    'chocolate cream makes the cake rich',
    'use eggs to help the cake rise',
    'use eggs to help the cookies hold shape',
    'a small cake needs flour sugar butter and eggs',
    'small cookies need flour sugar butter and eggs',
    'the cake pan goes into the oven',
    'the cookie tray goes into the oven',
    'the oven makes the cake warm and golden',
    'the oven makes the cookies warm and golden',
    'soft cake tastes good with cream',
    'soft cookies taste good with milk',
    'sweet cake and sweet cookies are simple treats',
    'fresh cake and fresh cookies smell good',
    'let the cake rest before you slice it',
    'let the cookies rest before you share them',
]


def get_training_examples(seed=2):
    examples = list(TRAINING_SENTENCES)
    random.Random(seed).shuffle(examples)
    return examples
