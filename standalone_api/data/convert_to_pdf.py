#!/usr/bin/env python3
from weasyprint import HTML
import os

def convert_html_to_pdf(html_file, pdf_file):
    """Конвертировать HTML файл в PDF"""
    try:
        print(f"Конвертация {html_file} в {pdf_file}...")

        # Конвертируем HTML в PDF
        HTML(html_file).write_pdf(pdf_file)

        print(f"✓ PDF успешно создан: {pdf_file}")
        print(f"Размер файла: {os.path.getsize(pdf_file) / 1024:.1f} KB")

        return True
    except Exception as e:
        print(f"✗ Ошибка при конвертации: {e}")
        return False

if __name__ == "__main__":
    html_path = "data/easter_eggs_article.html"
    pdf_path = "data/easter_eggs_article.pdf"

    if os.path.exists(html_path):
        success = convert_html_to_pdf(html_path, pdf_path)
        if success:
            print("\nPDF статья готова!")
        else:
            print("\nНе удалось создать PDF")
    else:
        print(f"Файл {html_path} не найден")