import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont


def setup_styles(system):
    """
    配置全局字体和样式
    返回: (UI字体, 粗体, 日志字体)
    """
    # 1. 定义字体
    if system == "Darwin":
        font_ui = tkfont.Font(family=".AppleSystemUIFont", size=13)
        font_bold = tkfont.Font(family=".AppleSystemUIFont", size=13, weight="bold")
        font_log = tkfont.Font(family="Menlo", size=12)
    else:
        font_ui = tkfont.Font(family="Microsoft YaHei UI", size=10)
        font_bold = tkfont.Font(family="Microsoft YaHei UI", size=10, weight="bold")
        font_log = tkfont.Font(family="Consolas", size=10)

    # 2. 配置 ttk 样式
    style = ttk.Style()
    try:
        if system == "Darwin":
            style.theme_use("clam")
        elif system == "Windows":
            style.theme_use("vista")
    except:
        pass  # 如果主题不存在，保持默认

    # 修复 Mac 下的按钮和列表背景色
    style.configure("TFrame", background="#f0f0f0")
    style.configure("TLabel", background="#f0f0f0")
    style.configure("TButton", font=font_ui)

    # 定义特殊样式
    style.configure("Fix.TButton", foreground="#E6a23c")  # 修复按钮用橙色
    style.configure("Big.TRadiobutton", font=font_ui)

    return font_ui, font_bold, font_log


def setup_paste_fix(widget, cmd_key, translations_dict):
    """
    为输入框添加右键菜单和快捷键修复 (解决 Mac Tkinter 无法粘贴的问题)
    :param widget: 目标 Entry 或 Text 组件
    :param cmd_key: "Command" (Mac) 或 "Control" (Win)
    :param translations_dict: 当前语言的翻译字典
    """
    # 简单的翻译映射，防止字典里缺key报错
    txt_paste = translations_dict.get("menu_paste", "Paste")
    txt_select_all = translations_dict.get("menu_select_all", "Select All")

    # 创建右键菜单
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label=txt_paste, command=lambda: do_paste(widget))
    menu.add_command(label=txt_select_all, command=lambda: select_all(widget))

    # 绑定右键点击
    if cmd_key == "Command":  # Mac
        widget.bind("<Button-2>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
    else:  # Win/Linux
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    # 绑定快捷键 (Mac Command+V / Win Ctrl+V)
    mod = "Meta" if cmd_key == "Command" else "Control"
    # 注意：Tkinter 的事件绑定格式通常是 <Command-v> 或 <Control-v>
    # 这里根据你的 _v6initial.py 逻辑稍微简化

    # 强制绑定粘贴事件
    widget.bind(f"<{cmd_key}-v>", lambda e: do_paste(widget))
    widget.bind(f"<{cmd_key}-a>", lambda e: select_all(widget))


def do_paste(widget):
    try:
        # 获取剪贴板内容
        text = widget.clipboard_get()
        if not text: return "break"

        # 如果有选中文本，先删除选中部分
        try:
            sel_first = widget.index("sel.first")
            sel_last = widget.index("sel.last")
            widget.delete(sel_first, sel_last)
        except tk.TclError:
            pass  # 没有选中

        # 插入光标处
        widget.insert(tk.INSERT, text)
        return "break"  # 阻止默认行为，防止重复粘贴
    except:
        pass


def select_all(widget):
    widget.select_range(0, tk.END)
    widget.icursor(tk.END)
    return "break"