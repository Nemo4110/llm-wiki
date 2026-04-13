#!/usr/bin/env python3
"""读取 PDF 文件内容的辅助脚本"""

import sys
import pdfplumber
import io

def read_pdf(pdf_path, pages=None):
    """读取 PDF 文件内容

    Args:
        pdf_path: PDF 文件路径
        pages: 要读取的页码范围，如 "1-10"，None 表示全部
    """
    # 强制 UTF-8 输出，绕开控制台编码问题
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    with pdfplumber.open(pdf_path) as pdf:
        if pages:
            # 解析页码范围
            if '-' in pages:
                start, end = map(int, pages.split('-'))
                page_nums = range(start - 1, end)  # 转为 0-indexed
            else:
                page_nums = [int(pages) - 1]

            for i in page_nums:
                if i < len(pdf.pages):
                    page = pdf.pages[i]
                    text = page.extract_text()
                    print(f"\n{'='*60}")
                    print(f"Page {i + 1}")
                    print(f"{'='*60}")
                    print(text)
        else:
            # 读取全部页面
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                print(f"\n{'='*60}")
                print(f"Page {i + 1}")
                print(f"{'='*60}")
                print(text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_pdf.py <pdf_path> [pages]")
        print("Example: python read_pdf.py document.pdf 1-10")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = sys.argv[2] if len(sys.argv) > 2 else None

    read_pdf(pdf_path, pages)
