text = "Кнжчипш щв шжувр тъюяпр"

# Проверим сдвиг 7 подробнее
def caesar_decrypt(text, shift):
    result = ""
    for char in text:
        if char.isalpha():
            if char.isupper():
                base = ord('А')
            else:
                base = ord('а')

            if 'А' <= char <= 'Я' or 'а' <= char <= 'я':
                shifted = (ord(char) - base - shift) % 32
                result += chr(base + shifted)
            else:
                result += char
        else:
            result += char
    return result

decrypted = caesar_decrypt(text, 7)
print(f"Исходный: {text}")
print(f"Сдвиг 7:  {decrypted}")
print()

# Проверим соответствие букв
print("Соответствие букв:")
for i, (orig, dec) in enumerate(zip(text, decrypted)):
    if orig != ' ':
        print(f"{orig} → {dec} (сдвиг {7})")