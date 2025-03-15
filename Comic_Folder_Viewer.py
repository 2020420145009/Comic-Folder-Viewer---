import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import sys
from math import ceil

class ComicViewer:
    def __init__(self, root):
        self.root = root
        self.current_path = '.'  # 初始路径设为当前目录
        self.history = []
        self.image_cache = {}    # 图片缓存
        self.visible_images = set()  # 当前可见图片
        self.is_image_mode = False  # 当前显示模式
        
        # 全屏设置
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        
        # 创建界面布局
        self._create_widgets()
        
        # 绑定快捷键
        self.root.bind('<BackSpace>', lambda e: self.navigate_back())
        self.root.bind('<Left>', self.handle_left)
        self.root.bind('<Right>', self.handle_right)
        self.root.bind('<Up>', self.handle_scroll_up)
        self.root.bind('<Down>', self.handle_scroll_down)
        
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 12))
        self.root.configure(background='#ffffff')
        self.scrollable_frame.configure(padding=10)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_program)

        # 添加缩放相关属性
        self.scale_factor = 1.0
        self.min_scale = 0.5
        self.max_scale = 3.0
        self.original_screen_width = root.winfo_screenwidth()

        # 绑定新的快捷键
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_scroll)

        self.load_content()

    def on_ctrl_scroll(self, event):
        """Ctrl+滚轮缩放处理"""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        """放大视图"""
        self.adjust_zoom(1.1)

    def zoom_out(self):
        """缩小视图"""
        self.adjust_zoom(0.9)

    def adjust_zoom(self, factor):
        """调整缩放比例核心方法"""
        new_scale = self.scale_factor * factor
        if self.min_scale <= new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self.refresh_images()
            self._keep_visible_position()

    def _keep_visible_position(self):
        """保持当前可视区域相对位置"""
        # 获取当前可视区域百分比
        y0, y1 = self.canvas.yview()
        # 刷新后重新定位
        self.root.after(100, lambda: self.canvas.yview_moveto(y0))

    def refresh_images(self):
        """刷新所有已加载图片"""
        # 仅刷新已缓存的图片
        for idx in list(self.image_cache.keys()):
            self._load_single_image(idx, refresh=True)
        
        # 更新布局和滚动区域
        self.scrollable_frame.update_idletasks()
        self._update_item_positions()
        self._update_scroll_region()
        self._lazy_load_images()

    def exit_program(self):
        """退出程序时的清理"""
        self.clear_cache()
        self.root.destroy()

    def clear_cache(self):
        """清理所有缓存（仅在退出时调用）"""
        self.image_cache.clear()
        self.visible_images.clear()

    def _create_widgets(self):
        """创建界面组件"""
        # 顶部标题区域（固定不滚动）
        self.header_frame = ttk.Frame(self.root)
        self.header_frame.pack(fill="x", side="top")
        
        # 返回按钮（固定在标题栏）
        self.back_button = ttk.Button(
            self.header_frame,
            text="← 返回上级",
            command=self.navigate_back,
            style='Big.TButton'
        )
        self.back_button.pack(side="left", padx=10)
        # self.back_button.pack_forget()  # 初始隐藏
        # 退出按钮（新增）
        self.quit_button = ttk.Button(
            self.header_frame,
            text="退出程序",
            command=self.exit_program,
            style='Big.TButton'
        )
        self.quit_button.pack(side="right", padx=10)
        # 标题标签
        self.title_label = ttk.Label(
            self.header_frame,
            font=('Arial', 20, 'bold'),
            anchor="center"
        )
        self.title_label.pack(fill="x", expand=True, pady=10)
        
         # 缩放按钮组（新增）
        zoom_frame = ttk.Frame(self.header_frame)
        zoom_frame.pack(side="left", padx=30)
        ttk.Button(zoom_frame, text="+ 放大", command=self.zoom_in).pack(side="left")
        ttk.Button(zoom_frame, text="- 缩小", command=self.zoom_out).pack(side="left", padx=5)
        

        # 滚动区域
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # 配置滚动
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="frame")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定事件
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)

    def _on_frame_configure(self, event):
        """当框架大小改变时更新滚动区域"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def handle_left(self, event):
        """左键处理：图片模式滚动，文件夹模式返回"""
        if self.is_image_mode:
            self._scroll_page('up')
        else:
            self.navigate_back()

    def handle_right(self, event):
        """右键处理：图片模式滚动"""
        if self.is_image_mode:
            self._scroll_page('down')

    def handle_scroll_up(self, event):
        """上键滚动"""
        self._scroll_page('up')

    def handle_scroll_down(self, event):
        """下键滚动"""
        self._scroll_page('down')
       
    def _get_sorted_items(self):
        """获取排序后的目录项"""
        try:
            items = os.listdir(self.current_path)
        except Exception as e:
            print(f"读取目录失败: {e}")
            return []
            
        # 处理中文文件名乱码
        items = [os.fsdecode(item) for item in items]
        
        # 排序：文件夹在前，文件在后，按名称排序
        items.sort(key=lambda x: (not os.path.isdir(os.path.join(self.current_path, x)), x.lower()))
        return items
  
    def _on_canvas_configure(self, event):
        """画布尺寸变化处理"""
        self.canvas.itemconfig("frame", width=event.width)
        self._lazy_load_images()

    def _on_mouse_wheel(self, event):
        """鼠标滚轮事件处理"""
        self.canvas.yview_scroll(-1*(event.delta//120), "units")
        self.root.after(50, self._lazy_load_images)

    def _scroll_page(self, direction):
        """翻页滚动"""
        page_height = self.canvas.winfo_height()
        current_pos = self.canvas.yview()[0]
        
        if direction == 'down':
            new_pos = current_pos + (page_height * 0.9) / self.scrollable_frame.winfo_height()
        else:
            new_pos = current_pos - (page_height * 0.9) / self.scrollable_frame.winfo_height()
        
        self.canvas.yview_moveto(max(0, min(new_pos, 1)))
        self.root.after(50, self._lazy_load_images)
        # self._keep_title_visible()

    def _keep_title_visible(self):
        pass
        """保持标题可见"""
        self.canvas.yview_moveto(0) if self.scrollable_frame.winfo_height() > 0 else None

    def clear_cache(self):
        """清理缓存"""
        for key in list(self.image_cache.keys()):
            if key not in self.visible_images:
                del self.image_cache[key]
        self.visible_images.clear()

    def _load_single_image(self, idx):
        """加载单个图片到缓存"""
        item = self.image_items[idx]
        full_path = os.path.join(self.current_path, item)
        
        try:
            img = Image.open(full_path)
            screen_width = self.root.winfo_screenwidth()
            w_percent = screen_width / float(img.size[0])
            h_size = int(img.size[1] * w_percent)
            img = img.resize((screen_width, h_size), Image.LANCZOS)
            self.image_cache[idx] = ImageTk.PhotoImage(img)
            
            # 创建图片标签
            label = ttk.Label(self.scrollable_frame, image=self.image_cache[idx])
            label.grid(row=idx, column=0, sticky="ew")
            
            # 立即更新位置信息（新增）
            self.scrollable_frame.update_idletasks()
            y1 = label.winfo_y()
            y2 = y1 + label.winfo_height()
            self.item_positions[idx] = (y1, y2)
            
        except Exception as e:
            print(f"加载失败: {full_path} - {e}")

    def _lazy_load_images(self):
        """改进后的懒加载逻辑"""
        if not hasattr(self, 'item_positions'):
            return
        
        # 获取可视区域范围
        canvas_top = self.canvas.canvasy(0)
        canvas_bottom = self.canvas.canvasy(self.canvas.winfo_height())
        
        count = 0
        # 计算当前可见的图片索引
        visible = set()
        for idx, (y1, y2) in enumerate(self.item_positions):
            # 扩展可视区域上下各一屏的缓冲范围
            buffer = self.canvas.winfo_height() * 0.5
            if (y1 - buffer) <= canvas_bottom and (y2 + buffer) >= canvas_top:
                visible.add(idx)
                if idx not in self.image_cache:
                    self._load_single_image(idx)
                    count += 1
            if count >= 3:
                break
        
        # 仅保留可见区域的图片（不清理缓存）
        self.visible_images = visible

    def load_content(self):
        """加载当前目录内容"""
        self.clear_cache()
        self.image_cache.clear()
        
        # 重置滚动
        self.canvas.yview_moveto(0)
        
        # 清空界面
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        start_row = 0
        
        items = self._get_sorted_items()
        
        if self._is_image_folder(items):
            self._setup_image_display(items, start_row)
            self.title_label.config(text=os.path.basename(self.current_path))
        else:
            self._show_subfolders(items, start_row)
            self.title_label.config(text="")

        self.scrollable_frame.update_idletasks()
        self._update_item_positions()
        self._lazy_load_images()

    def _is_image_folder(self, items):
        """判断是否是图片文件夹"""
        image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
        return all(
            os.path.splitext(item)[1].lower() in image_exts or
            os.path.isdir(os.path.join(self.current_path, item))
            for item in items
        ) and not any(os.path.isdir(os.path.join(self.current_path, item)) for item in items)
    
    def _update_item_positions(self):
        """记录所有项目的位置"""
        self.item_positions = []
        self.image_items = []
        
        for idx, widget in enumerate(self.scrollable_frame.winfo_children()):
            # if isinstance(widget, ttk.Label) and hasattr(widget, 'image') and widget.image:
            if isinstance(widget, ttk.Label) :
                y1 = widget.winfo_y()
                y2 = y1 + widget.winfo_height()
                # self.scrollable_frame.winfo_height += widget.winfo_height()
                self.item_positions.append((y1, y2))
                self.image_items.append(widget.cget("text"))

    def _setup_image_display(self, items, start_row = 0):
        """设置图片显示布局"""
        screen_width = self.root.winfo_screenwidth()
        self.scrollable_frame.columnconfigure(0, weight=1)
        
        for idx, item in enumerate(items):
            full_path = os.path.join(self.current_path, item)
            if os.path.isfile(full_path):
                label = ttk.Label(self.scrollable_frame)  # 空标签占位
                label.grid(row=start_row+idx, column=0, sticky="ew")
                label.config(text=item)  # 用text属性存储文件名

    def _show_subfolders(self, items, start_row = 0):
        """显示子文件夹"""
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 14))
        
        for idx, item in enumerate(items):
            full_path = os.path.join(self.current_path, item)
            if os.path.isdir(full_path):
                btn = ttk.Button(
                    self.scrollable_frame,
                    text=f"📁 {item}",
                    style='Big.TButton',
                    command=lambda p=full_path: self.navigate_to(p)
                )
                btn.grid(row=start_row+idx, column=0, sticky="ew", padx=10, pady=5)

    # 其他原有方法保持相同...
    
    def navigate_to(self, path):
        """导航到指定路径"""
        self.history.append(self.current_path)
        self.current_path = path
        self.load_content()
    
    def navigate_back(self):
        """返回上一级目录"""
        if self.history:
            self.current_path = self.history.pop()
            self.load_content()

            
if __name__ == "__main__":
    root = tk.Tk()
    root.title("漫画浏览器")
    app = ComicViewer(root)
    root.mainloop()