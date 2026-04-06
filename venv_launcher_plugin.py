import os
import sublime
import sublime_plugin

def _ps_quote(path: str) -> str:
    """把 Python 字符串安全地包成 PowerShell 的单引号字面量。"""
    if path is None:
        return "''"
    # PowerShell 单引号里转义规则：单引号 -> 两个单引号
    return "'" + str(path).replace("'", "''") + "'"

def build_cmd(env_root, workdir=None):
    """
    返回 (cmd, cwd)
    - cmd: 传给 terminus_open 的命令数组
    - cwd: 启动时的工作目录（建议设为 env_root）
    设计原则：
      1) 先 cd 到 env_root 再激活（避免相对路径找不到 venv）
      2) Activate.ps1 用绝对路径（更鲁棒）
      3) -NoExit + Clear-Host，激活后停留并清屏
      4) 可选再 Set-Location 到 workdir
    """
    cwd = env_root
    activate_ps1 = os.path.join(env_root, "Scripts", "Activate.ps1")
    lines = [
        f"Set-Location {_ps_quote(env_root)}",
        f"& {_ps_quote(activate_ps1)}",
    ]
    if workdir:
        lines.append(f"Set-Location {_ps_quote(workdir)}")
    # lines.append("Out-Host -Paging")

    ps_block = "& { " + "; ".join(lines) + " }"

    cmd = [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", ps_block,
    ]
    return cmd, cwd


class LaunchVenvQuickNewWindowCommand(sublime_plugin.WindowCommand):
    def run(self, next_command=None, next_args=None):
        self.view=self.window.active_view()
        self._next_command = next_command          # 保存调用方传入的命令名
        self._next_args = next_args or {}          # 命令参数（必须 JSON 化）
        settings = sublime.load_settings("venv_launcher.sublime-settings")
        self.envs = settings.get("envs", [])
        if not self.envs:
            sublime.message_dialog("No envs configured in venv_launcher.sublime-settings.")
            return
        items = []
        for e in self.envs:
            label = e.get("label")
            sub = e.get("workdir", "")
            items.append([str(label), str(sub)])
        self.window.show_quick_panel(items, self.on_done, placeholder="选择要激活的虚拟环境…")



    def on_done(self, idx):
        if idx == -1:
            return
        env = self.envs[idx]
        env_root = env.get("env_root") or ""       # NEW: 允许为空
        workdir  = env.get("workdir")
        title    = env.get("title") or env.get("label") or "venv"

        # --- 如果 env_root 配了，才检查并激活 ---
        if workdir and not os.path.isdir(workdir):
            sublime.message_dialog(f"workdir 不存在：{workdir}")
            return
        
        if env_root:
            activate_ps1 = os.path.join(env_root, "Scripts", "Activate.ps1")
            if not os.path.isdir(env_root):
                sublime.message_dialog(f"env_root 不存在：{env_root}")
                return
            if not os.path.isfile(activate_ps1):
                sublime.message_dialog(f"找不到激活脚本：{activate_ps1}")
                return

            cmd, cwd = build_cmd(env_root, workdir)   # 原逻辑
        
        else:
            # NEW: 没有 env_root → 不激活 venv，只切到 workdir
            cwd = workdir or os.path.expanduser("~")
            cmd = ["powershell", "-NoExit"]
            if cwd:
                cmd += ["-Command", f"Set-Location {cwd}"]

        sublime.run_command("new_window_place", {"w_px": 1295, "h_px": 683, "anchor": "bottom_right"})
        new_window = sublime.active_window()
        new_window.run_command("terminus_open", {"title": title,"cmd": cmd,"cwd": cwd,})
        new_window.set_minimap_visible(False)



        if self._next_command:
            from User.manim_plugins import find_terminus_sheet, send_terminus_command

            def wait_and_send(tries=80):
                sheet = find_terminus_sheet(self.view)  # 否则先全局找也行
                if sheet:
                    send_terminus_command(self._next_command, view=self.view,**self._next_args)
                else:
                    if tries > 0:
                        sublime.set_timeout(lambda: wait_and_send(tries-1), 50)
                    else:
                        sublime.status_message("⚠️ Terminus 未就绪（超时）。")

            sublime.set_timeout(lambda: wait_and_send(), 50)
