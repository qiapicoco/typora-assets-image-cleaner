import tkinter as tk
from tkinter import filedialog
import os
import re
import shutil


def find_used_images(md_file):
    used_images = []
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            pattern = r'!\[.*?\]\((.*?)\)'
            matches = re.findall(pattern, content)
            for match in matches:
                image_name = os.path.basename(match)
                used_images.append(image_name)
    except FileNotFoundError:
        result_text.insert(tk.END, f"错误: 文件 {md_file} 未找到。\n")
    return used_images


def clean_assets_folder():
    md_file = filedialog.askopenfilename(filetypes=[("Markdown文件", "*.md")])
    if not md_file:
        return
    assets_folder = os.path.splitext(md_file)[0] + '.assets'
    if not os.path.exists(assets_folder):
        result_text.insert(tk.END, f"错误: {assets_folder} 文件夹不存在。\n")
        return
    used_images = find_used_images(md_file)
    all_images = []
    for root, dirs, files in os.walk(assets_folder):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.svg', '.tiff', '.webp', '.gif')):
                all_images.append(file)
    result_text.insert(tk.END, f".assets 文件夹中的图片总数为{len(all_images)}\n")
    deleted_count = 0
    deleted_folder = os.path.join(assets_folder, 'deleted_images')
    if not os.path.exists(deleted_folder):
        os.makedirs(deleted_folder)
    for file in all_images:
        if file not in used_images:
            file_path = os.path.join(assets_folder, file)
            # 检查文件是否存在
            if os.path.exists(file_path):
                try:
                    shutil.move(file_path, os.path.join(deleted_folder, file))
                    result_text.insert(tk.END, f"图片已移动到 {deleted_folder}: {file}\n")
                    deleted_count += 1
                except Exception as e:
                    result_text.insert(tk.END, f"移动 {file} 时出错: {e}\n")
            else:
                result_text.insert(tk.END, f"文件 {file} 已不存在，跳过移动操作。\n")
    result_text.insert(tk.END, f"删除或移动到deleted_images文件夹的图片数量为 {deleted_count}\n")


root = tk.Tk()
root.title("Typora清理未引用图片")
root.geometry("790x500")
root.configure(bg="#ecf0f1")

button = tk.Button(root, text="选择Markdown文件并清理", command=clean_assets_folder,
                   font=("微软雅黑", 14), bg="#007BFF", fg="white", padx=20, pady=10)
button.pack(pady=20)

result_text = tk.Text(root, height=18, width=90, font=("微软雅黑", 10))
result_text.pack(pady=20)

root.mainloop()