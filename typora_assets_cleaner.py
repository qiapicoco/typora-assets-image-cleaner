import sys
import os
import re
import shutil
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QFileDialog, QWidget, QLabel,
                             QProgressBar, QMessageBox, QSplitter, QScrollArea,
                             QGroupBox, QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QDir
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor


class CleaningThread(QThread):
    """清理操作的工作线程，避免UI卡顿"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    finish_signal = pyqtSignal(int)
    found_image_signal = pyqtSignal(str, bool)  # 图片路径, 是否被使用

    def __init__(self, md_file, preview_limit=50):
        super().__init__()
        self.md_file = md_file
        self.assets_folder = os.path.splitext(md_file)[0] + '.assets'
        self.preview_limit = preview_limit
        self.preview_count = 0

    def run(self):
        try:
            start_time = time.time()
            self.update_signal.emit(f"开始分析文件: {os.path.basename(self.md_file)}\n")
            self.progress_signal.emit(5, "准备分析...")

            # 分析阶段 (5-25%)
            used_images = self.find_used_images()
            self.progress_signal.emit(15, "正在查找引用图片...")

            if not used_images:
                self.update_signal.emit("警告: 在Markdown文件中未找到引用的图片\n")

            all_images = self.get_all_images()
            if not all_images:
                self.update_signal.emit(f"错误: 在 {self.assets_folder} 中未找到图片文件\n")
                self.progress_signal.emit(100, "操作完成")
                self.finish_signal.emit(0)
                return

            total_images = len(all_images)
            self.update_signal.emit(f"在 {self.assets_folder} 中找到 {total_images} 张图片\n")
            self.progress_signal.emit(20, "正在分析图片引用...")

            unused_images = [img for img in all_images if img not in used_images]
            num_unused = len(unused_images)

            self.progress_signal.emit(25, f"找到 {num_unused} 张未引用的图片")
            self.update_signal.emit(f"其中 {num_unused} 张图片未在Markdown中引用\n")

            # 预览阶段 (25-40%)
            preview_progress_base = 25
            preview_progress_range = 15

            for i, img in enumerate(unused_images):
                if self.preview_count < self.preview_limit:
                    self.found_image_signal.emit(os.path.join(self.assets_folder, img), False)
                    self.preview_count += 1

                progress = preview_progress_base + int(preview_progress_range * i / max(1, len(unused_images) - 1))
                self.progress_signal.emit(progress, f"正在准备预览...")

            # 预览已使用的图片
            for i, img in enumerate(used_images[:min(5, len(used_images))]):
                self.found_image_signal.emit(os.path.join(self.assets_folder, img), True)

            self.progress_signal.emit(40, "预览准备完成")

            if not unused_images:
                self.update_signal.emit("没有需要清理的图片\n")
                self.progress_signal.emit(100, "清理完成")
                self.finish_signal.emit(0)
                return

            # 准备清理阶段 (40-50%)
            deleted_folder = os.path.join(self.assets_folder, 'deleted_images')
            self.update_signal.emit("开始清理未引用的图片...\n")
            self.progress_signal.emit(45, "准备清理...")

            # 清理阶段 (50-95%)
            cleanup_progress_base = 50
            cleanup_progress_range = 45

            for i, img in enumerate(unused_images):
                # 只有在第一次需要移动文件时才创建备份文件夹
                if i == 0 and not os.path.exists(deleted_folder):
                    os.makedirs(deleted_folder)
                    self.update_signal.emit(f"创建备份文件夹: {deleted_folder}\n")

                src_path = os.path.join(self.assets_folder, img)
                dst_path = os.path.join(deleted_folder, img)

                try:
                    if os.path.exists(src_path):
                        shutil.move(src_path, dst_path)
                        self.update_signal.emit(f"已移动: {img} -> deleted_images\n")
                    else:
                        self.update_signal.emit(f"文件不存在: {img} (已被移动?)\n")
                except Exception as e:
                    self.update_signal.emit(f"错误: 无法移动 {img}: {str(e)}\n")

                progress = cleanup_progress_base + int(cleanup_progress_range * i / max(1, num_unused - 1))
                self.progress_signal.emit(progress, f"已清理 {i + 1}/{num_unused}")

            # 完成阶段 (95-100%)
            end_time = time.time()
            elapsed = end_time - start_time
            self.update_signal.emit(f"\n清理完成！耗时: {elapsed:.2f} 秒\n")
            self.update_signal.emit(f"共移动 {num_unused} 张未引用的图片到备份文件夹\n")
            self.progress_signal.emit(98, "正在整理结果...")
            self.progress_signal.emit(100, "清理完成")
            self.finish_signal.emit(num_unused)

        except Exception as e:
            self.update_signal.emit(f"致命错误: {str(e)}\n")
            self.progress_signal.emit(100, "操作失败")
            self.finish_signal.emit(-1)

    def find_used_images(self):
        used_images = []
        try:
            with open(self.md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                patterns = [
                    r'!\[.*?\]\((.*?)\)',
                    r'\[.*?\]\((.*?)\)'
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        image_name = os.path.basename(match)
                        if image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.svg',
                                                        '.tiff', '.webp', '.gif')):
                            used_images.append(image_name)

            return list(set(used_images))

        except FileNotFoundError:
            self.update_signal.emit(f"错误: 文件 {self.md_file} 未找到\n")
            return []
        except Exception as e:
            self.update_signal.emit(f"错误: 读取文件时发生异常: {str(e)}\n")
            return []

    def get_all_images(self):
        all_images = []
        if not os.path.exists(self.assets_folder):
            self.update_signal.emit(f"错误: 文件夹 {self.assets_folder} 不存在\n")
            return []

        try:
            with os.scandir(self.assets_folder) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith(
                            ('.png', '.jpg', '.jpeg', '.bmp', '.svg', '.tiff', '.webp', '.gif')):
                        all_images.append(entry.name)
            return all_images
        except Exception as e:
            self.update_signal.emit(f"错误: 扫描文件夹时发生异常: {str(e)}\n")
            return []


class ImagePreviewWidget(QWidget):
    """图片预览小部件"""

    def __init__(self, image_path, is_used, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.is_used = is_used
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 增大内边距

        # 加载图片并调整大小 - 增大预览尺寸到400px
        pixmap = QPixmap(self.image_path)
        if pixmap.isNull():
            # 尝试添加更多错误处理，显示文件路径以便调试
            pixmap = QPixmap(400, 400)
            pixmap.fill(QColor(200, 200, 200))

        scaled_pixmap = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 增大尺寸

        # 创建图片标签
        image_label = QLabel()
        image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(400, 400)  # 增大最小尺寸
        image_label.setStyleSheet("""
            border: 2px solid #ddd; 
            border-radius: 8px; 
            padding: 5px;
            background-color: white;
        """)

        # 创建文件名标签
        file_name = os.path.basename(self.image_path)
        name_label = QLabel(file_name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(400)
        name_label.setFont(QFont("微软雅黑", 12))  # 增大字体

        # 创建状态标签
        status_label = QLabel("已使用" if self.is_used else "未使用")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet(
            f"color: {'green' if self.is_used else 'red'}; font-weight: bold; font-size: 14px;")  # 增大字体

        layout.addWidget(image_label)
        layout.addWidget(name_label)
        layout.addWidget(status_label)

    def mouseDoubleClickEvent(self, event):
        """双击事件处理 - 使用系统默认程序打开图片"""
        if event.button() == Qt.LeftButton:
            if os.path.exists(self.image_path):
                try:
                    if sys.platform.startswith('win'):
                        os.startfile(self.image_path)
                    elif sys.platform.startswith('darwin'):  # macOS
                        os.system(f'open "{self.image_path}"')
                    else:  # Linux
                        os.system(f'xdg-open "{self.image_path}"')
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法打开图片: {str(e)}")
            else:
                QMessageBox.warning(self, "文件不存在", f"图片文件不存在: {self.image_path}")


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thread = None
        self.current_md_file = None

    def init_ui(self):
        self.setWindowTitle("Typora清理未引用图片")
        self.setGeometry(300, 300, 1200, 750)  # 窗口尺寸

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 顶部信息栏优化
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #e9ecef; padding: 12px; border-radius: 8px; margin-bottom: 15px;")
        top_bar_layout = QHBoxLayout(top_bar)

        # 文件路径显示优化（相对路径）
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 打开文件夹按钮优化（更醒目）
        self.open_assets_btn = QPushButton("打开.assets文件夹")
        self.open_assets_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #ff4e4e;
            }
        """)
        self.open_assets_btn.setEnabled(False)
        self.open_assets_btn.clicked.connect(self.open_assets_folder)

        top_bar_layout.addWidget(self.file_path_label)
        top_bar_layout.addWidget(self.open_assets_btn, 0, Qt.AlignRight)  # 右对齐
        top_bar_layout.setSpacing(15)

        main_layout.addWidget(top_bar)

        # 分割器 - 左侧操作区，右侧预览区
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizes([382, 618])  # 调整比例

        # 左侧操作区优化
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)

        # 标题区域
        title_label = QLabel("Typora未引用图片清理工具")
        title_font = QFont("微软雅黑", 20, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title_label)

        desc_label = QLabel("此工具可帮助您清理Typora Markdown文件对应的.assets文件夹中未被引用的图片")
        desc_font = QFont("微软雅黑", 12)
        desc_label.setFont(desc_font)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        left_layout.addWidget(desc_label)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)
        button_layout.setContentsMargins(0, 15, 0, 0)

        self.select_button = QPushButton("选择Markdown文件并清理")
        self.select_button.setFont(QFont("微软雅黑", 14))
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #00c6a7;
                color: white;
                border-radius: 6px;
                padding: 12px 28px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #00a38d;
            }
        """)
        self.select_button.setMinimumHeight(50)
        self.select_button.clicked.connect(self.select_and_clean)
        button_layout.addWidget(self.select_button)

        left_layout.addLayout(button_layout)

        # 进度条区域优化
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)

        progress_label = QLabel("进度:")
        progress_label.setFont(QFont("微软雅黑", 12))

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ced4da;
                border-radius: 4px;
                height: 20px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #2196f3;
                width: 5px;
            }
        """)

        self.progress_text = QLabel("就绪")
        self.progress_text.setFont(QFont("微软雅黑", 12))

        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.progress_text)

        left_layout.addLayout(progress_layout)

        # 日志区域优化
        result_group = QGroupBox("操作日志")
        result_group.setFont(QFont("微软雅黑", 12, QFont.Bold))
        result_layout = QVBoxLayout(result_group)
        result_group.setMinimumHeight(250)  # 设置最小高度

        # 统一所有QGroupBox的样式设置
        group_box_style = """
            QGroupBox {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 0.7em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                background-color: transparent;
            }
        """

        result_group.setStyleSheet(group_box_style)

        self.result_text = QTextEdit()
        self.result_text.setFont(QFont("微软雅黑", 13))
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 12px;
                background-color: #f8f9fa;
                font-size: 13px;
            }
        """)
        result_layout.addWidget(self.result_text)

        left_layout.addWidget(result_group)

        # 右侧预览区优化
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = QGroupBox("图片预览")
        preview_group.setFont(QFont("微软雅黑", 12, QFont.Bold))
        preview_group.setMinimumHeight(500)  # 设置最小高度

        # 使用统一的QGroupBox样式
        preview_group.setStyleSheet(group_box_style)

        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # 图片预览滚动区域优化
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet("border: none;")

        self.preview_container = QWidget()
        self.preview_layout = QGridLayout(self.preview_container)
        self.preview_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_layout.setHorizontalSpacing(30)  # 增大间距
        self.preview_layout.setVerticalSpacing(25)
        self.preview_layout.setContentsMargins(15, 15, 15, 15)

        self.preview_scroll.setWidget(self.preview_container)
        preview_layout.addWidget(self.preview_scroll)

        right_layout.addWidget(preview_group)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter, 1) # 第二个参数为伸展因子，设为1表示允许扩展
        splitter.setSizes([577, 423])

        # 状态栏
        self.statusBar().setStyleSheet("font-size: 12px;")

        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow { background-color: #ffffff; }
            QGroupBox { 
                border: 1px solid #dee2e6; 
                border-radius: 6px; 
                margin-top: 0.7em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                background-color: transparent;
            }
            QTextEdit { 
                background-color: #f8f9fa; 
                color: #333;
                border: 1px solid #dee2e6;
            }
            QPushButton {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)

    def select_and_clean(self):
        """选择文件并开始清理"""
        self.result_text.clear()
        self.clear_previews()

        md_file, _ = QFileDialog.getOpenFileName(
            self, "选择Markdown文件", "", "Markdown文件 (*.md)"
        )

        if not md_file:
            return

        self.current_md_file = md_file
        self.current_assets_folder = os.path.splitext(md_file)[0] + '.assets'

        # 显示相对路径
        current_dir = QDir.currentPath()
        relative_path = QDir.toNativeSeparators(os.path.relpath(md_file, current_dir))
        self.file_path_label.setText(f"当前文件: {relative_path}")

        self.open_assets_btn.setEnabled(os.path.exists(self.current_assets_folder))

        self.statusBar().showMessage(f"正在分析: {os.path.basename(md_file)}")
        self.select_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_text.setText("准备中...")

        # 创建并启动工作线程
        self.thread = CleaningThread(md_file)
        self.thread.update_signal.connect(self.update_log)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finish_signal.connect(self.cleaning_finished)
        self.thread.found_image_signal.connect(self.add_image_preview)
        self.thread.start()

    def update_log(self, message):
        """更新日志文本"""
        self.result_text.append(message)
        self.result_text.moveCursor(self.result_text.textCursor().End)

    def update_progress(self, value, text):
        """更新进度条和进度文本"""
        self.progress_bar.setValue(value)
        self.progress_text.setText(text)

    def cleaning_finished(self, deleted_count):
        """清理完成后的处理"""
        if deleted_count >= 0:
            self.statusBar().showMessage(f"清理完成，共处理 {deleted_count} 张图片")
            QMessageBox.information(self, "清理完成",
                                    f"清理完成！\n共移动 {deleted_count} 张未引用图片到备份文件夹。")
        else:
            self.statusBar().showMessage("清理过程中发生错误")
            QMessageBox.critical(self, "清理失败", "清理过程中发生错误，请查看日志获取详细信息。")

        self.select_button.setEnabled(True)
        self.progress_text.setText("就绪")
        self.thread = None

    def add_image_preview(self, image_path, is_used):
        """添加图片预览（优化排列逻辑）"""
        # 计算每行可容纳的图片数量（根据当前宽度动态调整）
        container_width = self.preview_container.width()
        if container_width <= 0:
            return

        max_cols = max(1, (container_width - 30) // 420)  # 420=400(图片)+20(间距)
        current_count = self.preview_layout.count()
        row = current_count // max_cols
        col = current_count % max_cols

        preview_widget = ImagePreviewWidget(image_path, is_used)
        self.preview_layout.addWidget(preview_widget, row, col)

    def clear_previews(self):
        """清除所有图片预览"""
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def open_assets_folder(self):
        """打开.assets文件夹"""
        if hasattr(self, 'current_assets_folder') and os.path.exists(self.current_assets_folder):
            if sys.platform.startswith('win'):
                os.startfile(self.current_assets_folder)
            elif sys.platform.startswith('darwin'):
                os.system(f'open "{self.current_assets_folder}"')
            else:
                os.system(f'xdg-open "{self.current_assets_folder}"')

    def resizeEvent(self, event):
        """窗口大小改变时自动重新排列图片"""
        super().resizeEvent(event)
        if self.preview_layout.count() > 0:
            self.rearrange_previews()

    def rearrange_previews(self):
        """重新排列图片预览"""
        items = []
        while self.preview_layout.count():
            items.append(self.preview_layout.takeAt(0).widget())

        container_width = self.preview_container.width()
        if container_width <= 0:
            return

        max_cols = max(1, (container_width - 30) // 420)
        for i, widget in enumerate(items):
            row = i // max_cols
            col = i % max_cols
            self.preview_layout.addWidget(widget, row, col)


if __name__ == "__main__":
    os.environ["QT_FONT_DPI"] = "96"
    app = QApplication(sys.argv)
    font = QFont("微软雅黑", 11)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())