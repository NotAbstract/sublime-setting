from ctypes import Union
import sublime_plugin
import sublime
import os
import subprocess as sp
import threading
import re
def get_command(view, window):
    file_path = os.path.join(
        window.extract_variables()["file_path"],
        window.extract_variables()["file_name"],
    )
    # Pull out lines of file
    contents = view.substr(sublime.Region(0, view.size()))
    all_lines = contents.split("\n")

    # Find which lines define classes
    class_lines = [
        (line, all_lines.index(line))
        for line in contents.split("\n")
        if re.match(r"class (.+?)\((.+?)\):", line)
    ]

    # Where is the cursor
    row, col = view.rowcol(view.sel()[0].begin())

    # Find the first class defined before where the cursor is
    try:
        matching_class_str, scene_line_no = next(filter(
            lambda cl: cl[1] <= row,
            reversed(class_lines)
        ))
    except StopIteration:
        raise Exception("No matching classes")
    scene_name = matching_class_str[len("class "):matching_class_str.index("(")]

    cmds = ["manimgl", file_path, scene_name]
    # ----------------------------custom----------------------------
    if "zhixin" in file_path:
        cmds.append(f"--basefromfile")
    # ----------------------------custom----------------------------
    enter = False

    if row != scene_line_no:
        cmds.append("-se {}".format(row + 1))
        enter = True
        return " ".join(cmds), enter
        

    return " ".join(cmds), enter

def focus_terminus_when_ready(window, find_sheet, tries=80, interval=50):
    def tick(n):
        sheet = find_sheet()
        if not sheet:
            return sublime.set_timeout(lambda: tick(n-1), interval) if n > 0 else None

        v = sheet.view()
        if not v or v.is_loading():
            return sublime.set_timeout(lambda: tick(n-1), interval) if n > 0 else None

        if hasattr(window, "bring_to_front"):
            window.bring_to_front()
        window.focus_view(v)

    sublime.set_timeout(lambda: tick(tries), interval)

def send_terminus_command(
    command,
    clear=True,
    center=True,
    enter=True,
    view=None,
):
    # Find terminus window
    terminal_sheet = find_terminus_sheet(view)
    if terminal_sheet is None:
        return
    window = terminal_sheet.window()
    view = terminal_sheet.view()
    _, col = view.rowcol(view.size())

    # Ammend command with various keyboard shortcuts
    full_command = "".join([
        "\x7F" * col if clear else "",  # Bad hack
        "\x0C" if center else "",  # 换页
        command,
        "\n" if enter else ""
    ])

    window.run_command("terminus_send_string", {"string": full_command})
    def find_terminus_sheet_wrapper():
        return find_terminus_sheet(view)
    # focus_terminus_when_ready(window, find_terminus_sheet_wrapper)
    window.focus_view(view)

def checkpoint_paste_wrapper(view, arg_str=""):
    window = view.window()
    window.run_command("save")
    region = view.sel()[0]
    
    # Get start and end line numbers
    if not region.empty():
        start_line, _ = view.rowcol(region.begin())
        end_line, _ = view.rowcol(region.end())
    else:
        start_line = end_line = None  # 避免无用计算

    # Handle A world selection (non-empty, not a comment)
    if not region.empty() and start_line == end_line:
        selected_text = view.substr(region).lstrip()
        if not selected_text.startswith("#"):
            window = view.window()
            window.run_command("copy")
            command = view.substr(region)
            send_terminus_command(command,view=view)
            return

    # Expand selection to full lines
    window.run_command('change_sel')
    new_region = view.sel()[0]

    # Copy full lines
    view.window().run_command("copy")

    lines = view.substr(new_region).splitlines()
    first_line = lines[0].lstrip() if lines else ""
    starts_with_comment = first_line.startswith("#")

    if not starts_with_comment:
        terminus_paste_and_run(view)
        window.run_command('focus_window',args={"direction":"PygletWindow"})
        return
    else:
        comment = first_line if starts_with_comment else "#"
        command = f"checkpoint_paste({arg_str}) {comment} ({len(lines)} lines)"
        window.run_command('focus_window',args={"direction":"PygletWindow"})

    view.sel().clear()
    view.sel().add(sublime.Region(view.line(new_region.end()).begin()))

    send_terminus_command(command,view=view)

def get_target_name(view):
    if not view:
        return None
    file_path=view.window().extract_variables().get('file')
    view_name=view.name()
    if file_path:
        find_str=file_path
    elif view_name is not "":
        find_str=view_name
    else:
        return None
    target_name=None
    if "zhixin" in find_str:
        target_name="IPython:zhixin"
    elif "3b1b" in find_str:
        target_name="IPython:3b1b"
    elif "DanmakuRender" in find_str:
        target_name="IPython:danmu"
    return target_name

def terminus_paste_and_run(view):
    window=view.window()
    sel=view.sel()
    window.run_command("copy")
    end=view.sel()[0].end()
    sel.clear()
    sel.add(sublime.Region(end))
    terminal_sheet = find_terminus_sheet(view)
    terminal_window=terminal_sheet.window()
    terminal_window.run_command("terminus_send_string", {"string": "\x0C"})
    terminal_window.run_command("paste")
    terminal_window.run_command("terminus_send_string", {"string": "\n"})
    terminal_window.focus_view(terminal_sheet.view())

class CopyAndRun(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.window().run_command('change_sel')
        terminus_paste_and_run(self.view)


def find_terminus_sheet(view=None):
    targe_name=get_target_name(view)

    if view and targe_name:
        for win in sublime.windows():
            for sheet in win.sheets():
                name = sheet.view().name()
                if targe_name in name:
                    return sheet

    for win in sublime.windows():
        for sheet in win.sheets():
            name = sheet.view().name()
            if name == "Login Shell" or name.startswith("IPython:") or "Power Shell" in name:
                return sheet
    return None


class BuildWrapperCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        ext=view.window().extract_variables().get('file_extension')
        if ext != 'py':
            view.window().run_command('build')
            return
        # Expand selection to full lines
        sel = view.sel()
        region = view.sel()[0]
        start, end = region.begin(), region.end()
        if start ==end :
            view.window().run_command("save")
            file_name=view.window().extract_variables().get('file')
            command=f"python {file_name}"
            sublime.set_clipboard(command)
            send_terminus_command(command,view=view)
            return
class ManimRunScene(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        window = view.window()
        window.run_command("save")
        command, enter = get_command(view, window)
        sublime.set_clipboard(" --prerun --finder -o")
        # sublime.set_clipboard(" --prerun --finder -o --fps 60 -r '2048x2048' ")

        if find_terminus_sheet(view):
            send_terminus_command(command, enter=enter,view=view)
        else:
            window.run_command('launch_venv_quick_new_window', {
                            "next_command": command,
                            "next_args":{'enter':enter}
                        })


class ManimExit(sublime_plugin.TextCommand):
    def run(self, edit):
        send_terminus_command("quit",view=self.view)


class ManimCheckpointPaste(sublime_plugin.TextCommand):
    def run(self, edit):
        checkpoint_paste_wrapper(self.view)

class OpenFileDirectory(sublime_plugin.TextCommand):
    def run(self, edit):
        win = self.view.window()
        vars = win.extract_variables() if win else {}

        # 1) 获取文件路径；优先用视图绑定的文件，否则用提取变量
        file_path = self.view.file_name() or vars.get("file")
        if not file_path:
            sublime.status_message("当前视图没有绑定磁盘文件。")
            return

        # 2) 取目录（Sublime 自带的 ${file_path}）
        dir_path = vars.get("file_path") or os.path.dirname(file_path)
        dir_path = os.path.normpath(dir_path)

        # 3) 复制到剪贴板（可选）
        sublime.set_clipboard(dir_path)
        sublime.status_message("目录已复制并将交给 AHK：{}".format(dir_path))

        # 4) 调用 AHK（传参）
        ahk_script = r"C:\Users\zhixin\Documents\AutoHotkey\filexplorer.ahk"
        ahk_exe    = r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe"  # 如为便携版/路径不同请改

        def run_ahk():
            try:
                # 首选指定 v2 可执行文件，避免系统未关联 .ahk
                sp.run([ahk_exe, ahk_script, dir_path], check=True)
            except FileNotFoundError:
                # 退回用系统关联方式执行（.ahk 关联到 AutoHotkey）
                sp.run([ahk_script, dir_path], shell=True, check=True)
            except Exception as e:
                sublime.error_message("调用 AHK 失败：{}".format(e))

        threading.Thread(target=run_ahk, daemon=True).start()


class ManimRecordedCheckpointPaste(sublime_plugin.TextCommand):
    def run(self, edit):
        checkpoint_paste_wrapper(self.view, arg_str="record=True")


class ManimSkippedCheckpointPaste(sublime_plugin.TextCommand):
    def run(self, edit):
        checkpoint_paste_wrapper(self.view, arg_str="skip=True")




class CommentFold(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        regions = view.sel()
        regions_to_fold = []
        for region in regions:
            reg_str = view.substr(region)

            lines = reg_str.split("\n")
            view_index = region.begin()

            indent_level = None
            last_full_line_end = view_index
            last_comment_line_end = None
            last_line_was_comment = False
            for line in lines:
                line_end_point = view_index + len(line)
                if line.lstrip().startswith("#"):
                    if indent_level is None:
                        indent_level = len(line) - len(line.lstrip())
                    if len(line) - len(line.lstrip()) == indent_level and not last_line_was_comment:
                        if last_comment_line_end:
                            regions_to_fold.append(sublime.Region(
                                last_comment_line_end,
                                last_full_line_end,
                            ))
                        last_comment_line_end = line_end_point
                else:
                    last_line_was_comment = False
                if line.strip():
                    last_full_line_end = line_end_point
                view_index = line_end_point + 1
            if last_comment_line_end:
                regions_to_fold.append(sublime.Region(
                    last_comment_line_end, region.end(),
                ))
        self.view.fold(regions_to_fold)
