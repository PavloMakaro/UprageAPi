def caesar_decrypt(text, shift):
    result = ""
    for char in text:
        if char.isalpha():
            if char.isupper():
                base = ord('А')
            else:
                base = ord('а')

            # Русский алфавит
            if 'А' <= char <= 'Я' or 'а' <= char <= 'я':
                shifted = (ord(char) - base - shift) % 32
                result += chr(base + shifted)
            else:
                result += char
        else:
            result += char
    return result

text = "Кнжчипш щв шжувр тъюяпр"
print("Исходный текст:", text)
print("\nПопробуем разные сдвиги:")
for shift in range(1, 33):
    decrypted = caesar_decrypt(text, shift)
    print(f"Сдвиг {shift:2d}: {decrypted}")