import sublime, sublime_plugin,time
import ctypes
from ctypes import wintypes
# ---------------- user32 & consts (once) ----------------
user32 = ctypes.windll.user32
SW_SHOWNORMAL     = 1
SW_SHOWMINIMIZED  = 2
SW_SHOWMAXIMIZED  = 3
SW_RESTORE        = 9
GW_OWNER          = 4  # 如需排除拥有者窗口可用
# ---- prototypes (一次声明，防止类型错传/加速调用) ----
user32.IsIconic.argtypes             = (wintypes.HWND,)
user32.IsIconic.restype              = wintypes.BOOL

user32.IsWindowVisible.argtypes      = (wintypes.HWND,)
user32.IsWindowVisible.restype       = wintypes.BOOL

user32.ShowWindow.argtypes           = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype            = wintypes.BOOL

user32.SetForegroundWindow.argtypes  = (wintypes.HWND,)
user32.SetForegroundWindow.restype   = wintypes.BOOL

user32.EnumWindows.argtypes          = (ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM)
user32.EnumWindows.restype           = wintypes.BOOL

user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype  = ctypes.c_int

user32.GetWindowTextW.argtypes       = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype        = ctypes.c_int

user32.GetWindowRect.argtypes        = (wintypes.HWND, ctypes.POINTER(ctypes.c_long * 4),)
user32.GetWindowRect.restype         = wintypes.BOOL

user32.GetWindow.argtypes = (wintypes.HWND, ctypes.c_uint)
user32.GetWindow.restype  = wintypes.HWND
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
class FocusWindowCommand(sublime_plugin.TextCommand):
    def run(self, edit, direction="left"):
        if direction == "left":
            sublime.set_timeout_async(self.focus_leftmost_window, 0)
        elif direction == "right":
            sublime.set_timeout_async(self.focus_rightmost_window, 0)
        elif direction == "PygletWindow":
            sublime.set_timeout_async(self.focus_PygletWindow, 0)
    def focus_PygletWindow(self):
        hwnds = self.enum_windows(text='PygletWindow')
        for hwnd in hwnds:
            title=self.get_title(hwnd)
            if title == 'PygletWindow':
                self.bring_to_front(hwnd)
                # user32.SetActiveWindow(hwnd)
                # user32.SetForegroundWindow(hwnd)

    def focus_leftmost_window(self):
        hwnds = self.enum_windows(text='Sublime Text')
        leftmost_hwnd = None
        leftmost_x = None
        for hwnd in hwnds:
           if self.is_min(hwnd):
               continue  # 跳过最小化的窗口
           x, y, w, h = self.get_position(hwnd)
           if leftmost_x is None or x < leftmost_x:
               leftmost_x = x
               leftmost_hwnd = hwnd

        if leftmost_hwnd:
           title = self.get_title(leftmost_hwnd)
           self.focus(leftmost_hwnd)
        else:
           return
    def focus_rightmost_window(self):
        hwnds = self.enum_windows(text='Sublime Text')
        leftmost_hwnd = None
        rightmost_x = None
        for hwnd in hwnds:
           if self.is_min(hwnd):
               continue  # 跳过最小化的窗口
           x, y, w, h = self.get_position(hwnd)
           if rightmost_x is None or x > rightmost_x:
               rightmost_x = x
               leftmost_hwnd = hwnd

        if leftmost_hwnd:
           title = self.get_title(leftmost_hwnd)
           self.focus(leftmost_hwnd)
        else:
           return

    def restore(self,hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    def max(self,hwnd):
        user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)

    def is_min(self, hwnd):
        return bool(user32.IsIconic(hwnd))
    def bring_to_front(self,hwnd):
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,SWP_NOMOVE | SWP_NOSIZE)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,SWP_NOMOVE | SWP_NOSIZE)

    def focus(self, hwnd):
        if self.is_min(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)

    def get_position(self, hwnd):
        return list(self.get_window_rect(hwnd))  # [x, y, w, h]
    def get_window_rect(self,hwnd):
        buf = (ctypes.c_long * 4)()
        if not user32.GetWindowRect(hwnd, ctypes.byref(buf)):
            raise ctypes.WinError()
        left, top, right, bottom = buf
        return left, top, right - left, bottom - top  # x, y, w, h

    def get_title(self,hwnd):
        length = user32.GetWindowTextLengthW(hwnd)  # 标题长度
        buf = ctypes.create_unicode_buffer(length + 1)  # 多分配一个给 \0
        chars = user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def is_visible(self,hwnd):
        return bool(user32.IsWindowVisible(hwnd))
    def enum_windows(self,text='Sublime Text'):
        EnumProc  = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        hwnds = []

        @EnumProc
        def callback(hwnd, lParam):
            # 快速过滤：不可见直接跳过
            if not self.is_visible(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value
            if text in title:
                hwnds.append(hwnd)
            return True

        user32.EnumWindows(callback, 0)
        return hwnds




class NewWindowPlaceCommand(sublime_plugin.ApplicationCommand):
    """
    用法示例（Console）：
      sublime.run_command("new_window_place", 
      {"w_px": 1280, "h_px": 720, "anchor": "top_left"})
      sublime.run_command("new_window_place", 
      {"w_ratio": 0.5, "h_ratio": 0.5, "anchor": "bottom_right"})
    参数：
      w_px/h_px 优先；否则用 w_ratio/h_ratio（0~1）
      anchor: "top_left" | "top_right" | "bottom_left" | "bottom_right"
    """
    def run(self, w_px=None, h_px=None, w_ratio=0.5, h_ratio=0.5, anchor="bottom_right"):
        sublime.run_command("new_window")
        sublime.set_timeout_async(lambda: self._place(w_px, h_px, w_ratio, h_ratio, anchor), 0)

    def _place(self, w_px, h_px, w_ratio, h_ratio, anchor):
        u32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        MONITOR_DEFAULTTONEAREST = 2
        SWP_NOZORDER, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0004, 0x0010, 0x0040

        # DPI 感知（Per-Monitor v2）
        try:
            u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

        def get_ext_rect(hwnd):
            r = RECT()
            if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) == 0:
                return r
            return None

        # 等前台窗口（≤1.2s）
        hwnd, waited = None, 0
        while waited <= 1200:
            hwnd = u32.GetForegroundWindow()
            if hwnd: break
            time.sleep(0.05); waited += 50
        if not hwnd: return

        # 当前显示器“工作区”
        hmon = u32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not u32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
            rcw = RECT(0, 0, sw, sh)
        else:
            rcw = mi.rcWork

        work_w = rcw.right - rcw.left
        work_h = rcw.bottom - rcw.top

        # 初始尺寸
        if isinstance(w_px, int) and isinstance(h_px, int):
            w = max(100, min(w_px, work_w))
            h = max(100, min(h_px, work_h))
        else:
            w = max(100, int(work_w * float(w_ratio)))
            h = max(100, int(work_h * float(h_ratio)))

        # 初始位置
        if anchor == "top_left":
            x, y = rcw.left, rcw.top
        elif anchor == "top_right":
            x, y = rcw.right - w, rcw.top
        elif anchor == "bottom_left":
            x, y = rcw.left, rcw.bottom - h
        else:  # bottom_right
            x, y = rcw.right - w, rcw.bottom - h

        # 第一次安放
        u32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h),
                         SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)

        # 读取外框，精确贴边（移动纠偏 + 尺寸收边）
        ext = get_ext_rect(hwnd)
        if not ext: return

        # 先把锚定边对齐
        if "left" in anchor:   x += (rcw.left  - ext.left)
        if "top"  in anchor:   y += (rcw.top   - ext.top)
        if "right" in anchor:  x += (rcw.right - ext.right)
        if "bottom" in anchor: y += (rcw.bottom- ext.bottom)
        u32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h),
                         SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)

        # 再次读取外框，处理另一侧越界
        ext2 = get_ext_rect(hwnd)
        if not ext2: return

        # 左/上越界：平移并缩小尺寸；右/下越界：仅缩小尺寸
        if ext2.left < rcw.left:
            dx = rcw.left - ext2.left
            x += dx; w = max(100, w - dx)
        if ext2.top < rcw.top:
            dy = rcw.top - ext2.top
            y += dy; h = max(100, h - dy)
        if ext2.right > rcw.right:
            dw = ext2.right - rcw.right
            w = max(100, w - dw)
        if ext2.bottom > rcw.bottom:
            dh = ext2.bottom - rcw.bottom
            h = max(100, h - dh)

        u32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h),
                         SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)
