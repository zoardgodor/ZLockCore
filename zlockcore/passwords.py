import math
import string


def strength(password: str) -> tuple[int, str]:
    if not password:
        return 0, 'empty'
    pool = 0
    if any(char.islower() for char in password):
        pool += 26
    if any(char.isupper() for char in password):
        pool += 26
    if any(char.isdigit() for char in password):
        pool += 10
    if any(char in string.punctuation for char in password):
        pool += len(string.punctuation)
    entropy = len(password) * math.log2(max(pool, 1))
    if len(password) < 8 or entropy < 35:
        return 1, 'weak'
    if len(password) < 12 or entropy < 60:
        return 2, 'medium'
    return 3, 'strong'
