import sublime
import sublime_plugin
import re
def is_point_visible(view, pt: int) -> bool:
    return view.visible_region().contains(pt)

class AlignEqualsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for region in self.view.sel():
            if region.empty():
                continue

            line_regions = self.view.lines(region)
            lines_data = []
            max_eq_pos = -1

            # 正则表达式说明：
            # (?<![!<>=])  表示左边不能是 ! < > =
            # =            匹配等号本身
            # (?![=])      表示右边不能是 =
            eq_regex = re.compile(r'(?<![!<>=])=(?![=])')

            # 第一遍扫描：计算位置
            for line_reg in line_regions:
                line_str = self.view.substr(line_reg)
                # 使用正则查找第一个真正的“赋值等号”
                match = eq_regex.search(line_str)

                if match:
                    eq_idx = match.start()
                    left_part = line_str[:eq_idx].rstrip()
                    right_part = line_str[eq_idx+1:].lstrip()

                    max_eq_pos = max(max_eq_pos, len(left_part))
                    lines_data.append((line_reg, left_part, right_part))
                else:
                    lines_data.append((line_reg, None, line_str))

            # 第二遍扫描：应用对齐
            for line_reg, left, right in reversed(lines_data):
                if left is not None:
                    padding = " " * (max_eq_pos - len(left) + 1)
                    # 确保等号后只有一个空格
                    new_line = f"{left}{padding}= {right}"
                    self.view.replace(edit, line_reg, new_line)

class FindPrevExpandCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        sels = view.sel()
        # 若没有任何非空选区，先建立基准（等价第一次 Ctrl+D）
        if all(r.empty() for r in sels):
            view.run_command("find_under_expand")
            return

        # 备份当前选区 (old)
        old = list(sels)

        # 拿到“所有匹配”的 Region
        # view.run_command("find_all_under")
        # all_regs = list(view.sel())
        search_term = view.substr(sels[0]) # 获取当前光标下的单词
        all_regs = view.find_all(search_term, sublime.LITERAL)

        # 恢复 old 选区
        view.sel().clear()
        for r in old:
            view.sel().add(r)

        # 计算 old 的最小/最大 (row, col)
        def rc(region):
            return view.rowcol(region.begin())  # (row, col)

        min_rc = min(rc(r) for r in old)   # 最小 (row, col)
        max_rc = max(rc(r) for r in old)   # 最大 (row, col)

        # 分块：
        # 第一块：严格小于 min_rc（先比较 row，再比较 col）
        first_block  = [r for r in all_regs if rc(r) <  min_rc]
        # 第二块：剩下的
        second_block = [r for r in all_regs if r not in first_block]
        # 选择块：优先第一块；若空，则用第二块
        blocks = [first_block, second_block if not first_block else []]

        # 依照块顺序处理；块内按 (row,col) 倒序，从后往前加；加到一个就 return
        for block in blocks:
            for r in sorted(block, key=rc, reverse=True):
                # 避免重复
                if all(not (r == s) for s in view.sel()):
                    view.sel().add(r)
                    if not is_point_visible(view,r.begin()):
                        view.show_at_center(r.begin())
                    return
        
# class PlusLineCommand(sublime_plugin.TextCommand):
# 	def run(self, edit, lines = 10):
# 		(row,col) = self.view.rowcol(self.view.sel()[0].begin())
# 		self.view.run_command("goto_line", {"line": row+1 + lines})


# class MinusLineCommand(sublime_plugin.TextCommand):
# 	def run(self, edit, lines = 10):
# 		(row,col) = self.view.rowcol(self.view.sel()[0].begin())
# 		self.view.run_command("goto_line", {"line": row+1 - lines})

# class GoToBeginCommand(sublime_plugin.TextCommand):
# 	def run(self, edit):
# 		(row,col) = self.view.rowcol(self.view.sel()[0].begin())
# 		self.view.run_command("goto_line", {"line": row+1})

# class GoToEndCommand(sublime_plugin.TextCommand):
# 	def run(self, edit):
# 		(row,col) = self.view.rowcol(self.view.sel()[0].end())
# 		self.view.run_command("goto_line", {"line": row+1})
# 		self.view.run_command("move_to",{"to":"eol"})
# class SelectBetweenCursorsCommand(sublime_plugin.TextCommand):
#     def run(self, edit):
#         start=self.view.sel()[0].begin()
#         end=self.view.sel()[0].end()
#         start_line=self.view.line(start)
#         end_line=self.view.line(end)
#         new_start=start_line.begin()
#         new_end=end_line.end()
#         self.view.sel().add(sublime.Region(new_start, new_end))

class ChangeSelCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        sel = view.sel()[0]

        if sel.empty():
            line = view.line(sel.begin())
            view.sel().clear()
            view.sel().add(line)
            return

        region_begin = sel.begin()
        region_end = sel.end() - 1 if sel.end() > 0 else 0  # lock to last real char

        first_line = view.line(region_begin)
        last_line  = view.line(region_end)

        first_line_sel = sublime.Region(region_begin, first_line.end())
        last_line_sel  = sublime.Region(last_line.begin(), sel.end())

        first_line_text = view.substr(first_line_sel).strip()
        last_line_text  = view.substr(last_line_sel).strip()

        # --- 起点：若首行片段是空，就向下扫描到第一条非空行 ---
        if first_line_text != '':
            new_begin = first_line.begin()
        else:
            # move down until non-empty
            p = first_line.end() + 1
            new_begin = first_line.end()  # fallback
            while p < view.size():
                ln = view.line(p)
                if view.substr(ln).strip() != '':
                    new_begin = ln.begin()
                    break
                p = ln.end() + 1

        # --- 终点：若末行片段是空，就向上扫描到第一条非空行 ---
        if last_line_text != '':
            new_end = last_line.end()
        else:
            # move up until non-empty
            # 注意：last_line.begin() 可能为 0
            p = last_line.begin() - 1
            new_end = last_line.begin()  # fallback
            while p >= 0:
                ln = view.line(p)
                if view.substr(ln).strip() != '':
                    new_end = ln.end()
                    break
                p = ln.begin() - 1

        # 选区整体全空：只把光标落在 new_begin（你原有逻辑）
        if view.substr(sel).strip() == '':
            view.sel().clear()
            view.sel().add(sublime.Region(region_end, region_end))
            return

        # 规范化应用（避免反向 / crossing）
        if new_begin < new_end:
            view.sel().clear()
            view.sel().add(sublime.Region(new_begin, new_end))
        else:
            view.sel().clear()
            view.sel().add(sublime.Region(new_begin, new_begin))





