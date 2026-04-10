import os
import sys
import subprocess
import time
import glob
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import signal


class AbaqusJobSubmitter:
    def __init__(self, root):
        self.root = root
        self.root.title("Abaqus 2024 批量任务提交工具")
        self.root.geometry("1000x800")
        
        # 存储inp文件列表及其顺序
        self.inp_files = []
        self.selected_indices = set()
        self.current_job_index = 0
        self.is_running = False
        self.should_stop = False
        self.should_terminate = False
        
        # Abaqus命令名称
        self.abaqus_cmd = "abq2024"
        
        # CPU核心数
        self.cpu_count = 8
        
        # 当前运行的进程
        self.current_process = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        # 顶部控制区域
        control_frame = tk.Frame(self.root, padx=10, pady=5)
        control_frame.pack(fill=tk.X)
        
        # 选择文件夹按钮
        tk.Button(control_frame, text="选择文件夹", command=self.select_folder, 
                 bg="#4CAF50", fg="white", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        
        # 刷新文件列表按钮
        tk.Button(control_frame, text="刷新文件列表", command=self.refresh_file_list, 
                 font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        
        # Abaqus命令名称设置
        abq_frame = tk.Frame(control_frame)
        abq_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(abq_frame, text="Abaqus命令:", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.abq_entry = tk.Entry(abq_frame, width=15, font=("微软雅黑", 10))
        self.abq_entry.insert(0, self.abaqus_cmd)
        self.abq_entry.pack(side=tk.LEFT, padx=3)
        
        # CPU核心数输入
        cpu_frame = tk.Frame(control_frame)
        cpu_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(cpu_frame, text="CPU核心数:", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.cpu_entry = tk.Entry(cpu_frame, width=5, font=("微软雅黑", 10))
        self.cpu_entry.insert(0, "8")
        self.cpu_entry.pack(side=tk.LEFT, padx=3)
        
        # 全选/取消全选按钮
        tk.Button(control_frame, text="全选", command=self.select_all, 
                 font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="取消全选", command=self.deselect_all, 
                 font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        
        # 上移/下移按钮
        tk.Button(control_frame, text="↑ 上移", command=self.move_up, 
                 font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="↓ 下移", command=self.move_down, 
                 font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        
        # 中间文件列表区域
        list_frame = tk.Frame(self.root, padx=10, pady=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(list_frame, text="INP文件列表（双击切换选中状态，使用上移/下移调整顺序）：", 
                font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        
        # 创建带滚动条的列表框
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, 
                                       yscrollcommand=scrollbar.set,
                                       font=("Consolas", 10), height=15)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # 绑定双击事件切换选中状态
        self.file_listbox.bind('<Double-Button-1>', self.toggle_selection)
        
        # 底部控制和日志区域
        bottom_frame = tk.Frame(self.root, padx=10, pady=5)
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控制按钮
        btn_frame = tk.Frame(bottom_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="开始提交任务", command=self.start_submission, 
                 bg="#2196F3", fg="white", font=("微软雅黑", 11, "bold"),
                 width=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="停止当前任务", command=self.stop_current_job, 
                 bg="#FF9800", fg="white", font=("微软雅黑", 11, "bold"),
                 width=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="终止所有任务", command=self.terminate_all_jobs, 
                 bg="#f44336", fg="white", font=("微软雅黑", 11, "bold"),
                 width=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="清空日志", command=self.clear_log, 
                 font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=5)
        
        # 日志显示区域
        tk.Label(bottom_frame, text="运行日志：", font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        
        log_frame = tk.Frame(bottom_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_scrollbar = tk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, 
                                                  yscrollcommand=log_scrollbar.set,
                                                  font=("Consolas", 9), height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)
        
        # 配置日志文本标签颜色
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("warning", foreground="orange")
    
    def log_message(self, message, tag="info"):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
    
    def select_folder(self):
        """选择文件夹"""
        folder_path = filedialog.askdirectory(title="选择包含INP文件的文件夹")
        if folder_path:
            self.folder_path = folder_path
            self.log_message(f"已选择文件夹: {folder_path}", "info")
            self.scan_inp_files()
    
    def scan_inp_files(self):
        """扫描文件夹下的INP文件"""
        if not hasattr(self, 'folder_path'):
            messagebox.showwarning("警告", "请先选择文件夹！")
            return
        
        self.inp_files = []
        inp_pattern = os.path.join(self.folder_path, "*.inp")
        files = glob.glob(inp_pattern)
        
        # 按文件名排序
        files.sort(key=lambda x: os.path.basename(x).lower())
        
        for file_path in files:
            filename = os.path.basename(file_path)
            self.inp_files.append({
                'path': file_path,
                'name': filename,
                'job_name': Path(filename).stem
            })
        
        self.refresh_file_list()
        self.log_message(f"扫描到 {len(self.inp_files)} 个INP文件", "success")
    
    def refresh_file_list(self):
        """刷新文件列表显示"""
        self.file_listbox.delete(0, tk.END)
        
        for idx, file_info in enumerate(self.inp_files):
            status = "✓ " if idx in self.selected_indices else "□ "
            display_text = f"{status}{file_info['name']}"
            self.file_listbox.insert(tk.END, display_text)
    
    def toggle_selection(self, event=None):
        """切换选中状态"""
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            if index in self.selected_indices:
                self.selected_indices.remove(index)
            else:
                self.selected_indices.add(index)
            self.refresh_file_list()
    
    def select_all(self):
        """全选"""
        for i in range(len(self.inp_files)):
            self.selected_indices.add(i)
        self.refresh_file_list()
    
    def deselect_all(self):
        """取消全选"""
        self.selected_indices.clear()
        self.refresh_file_list()
    
    def move_up(self):
        """上移选中的文件"""
        selection = self.file_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index > 0:
            # 交换位置
            self.inp_files[index], self.inp_files[index - 1] = \
                self.inp_files[index - 1], self.inp_files[index]
            
            # 更新选中索引
            new_selected = set()
            for idx in self.selected_indices:
                if idx == index:
                    new_selected.add(index - 1)
                elif idx == index - 1:
                    new_selected.add(index)
                else:
                    new_selected.add(idx)
            self.selected_indices = new_selected
            
            self.refresh_file_list()
            self.file_listbox.selection_set(index - 1)
    
    def move_down(self):
        """下移选中的文件"""
        selection = self.file_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.inp_files) - 1:
            # 交换位置
            self.inp_files[index], self.inp_files[index + 1] = \
                self.inp_files[index + 1], self.inp_files[index]
            
            # 更新选中索引
            new_selected = set()
            for idx in self.selected_indices:
                if idx == index:
                    new_selected.add(index + 1)
                elif idx == index + 1:
                    new_selected.add(index)
                else:
                    new_selected.add(idx)
            self.selected_indices = new_selected
            
            self.refresh_file_list()
            self.file_listbox.selection_set(index + 1)
    
    def start_submission(self):
        """开始提交任务"""
        # 获取Abaqus命令名称
        self.abaqus_cmd = self.abq_entry.get().strip()
        if not self.abaqus_cmd:
            messagebox.showwarning("警告", "请输入Abaqus命令名称！")
            return
        
        # 获取CPU核心数
        try:
            self.cpu_count = int(self.cpu_entry.get())
            if self.cpu_count < 1:
                messagebox.showwarning("警告", "CPU核心数必须大于0！")
                return
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的CPU核心数！")
            return
        
        if not self.selected_indices:
            messagebox.showwarning("警告", "请至少选择一个INP文件！")
            return
        
        if self.is_running:
            messagebox.showwarning("警告", "任务正在运行中！")
            return
        
        # 获取选中且排序后的文件列表
        self.job_queue = [self.inp_files[i] for i in sorted(self.selected_indices)]
        self.current_job_index = 0
        self.is_running = True
        self.should_stop = False
        self.should_terminate = False
        
        self.log_message("=" * 60, "info")
        self.log_message(f"开始批量提交任务，共 {len(self.job_queue)} 个任务", "success")
        self.log_message(f"Abaqus命令: {self.abaqus_cmd}", "info")
        self.log_message(f"CPU核心数: {self.cpu_count}", "info")
        self.log_message("=" * 60, "info")
        
        # 在新线程中运行任务
        thread = threading.Thread(target=self.run_jobs)
        thread.daemon = True
        thread.start()
    
    def stop_current_job(self):
        """停止当前正在运行的任务"""
        if not self.is_running:
            messagebox.showinfo("提示", "当前没有正在运行的任务！")
            return
        
        if messagebox.askyesno("确认", "确定要停止当前正在计算的任务吗？\n停止后将自动继续下一个任务。"):
            self.should_stop = True
            self.log_message("正在停止当前任务...", "warning")
            
            # 终止当前进程
            if self.current_process:
                try:
                    # Windows下使用taskkill终止进程及其子进程
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.current_process.pid)])
                    self.log_message("已终止当前Abaqus进程", "warning")
                except Exception as e:
                    self.log_message(f"终止进程时出错: {e}", "error")
    
    def terminate_all_jobs(self):
        """终止所有任务"""
        if not self.is_running:
            messagebox.showinfo("提示", "当前没有正在运行的任务！")
            return
        
        if messagebox.askyesno("确认", "确定要终止所有任务吗？\n这将停止当前任务并取消剩余所有任务。"):
            self.should_terminate = True
            self.should_stop = True
            self.log_message("正在终止所有任务...", "warning")
            
            # 终止当前进程
            if self.current_process:
                try:
                    # Windows下使用taskkill终止进程及其子进程
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.current_process.pid)])
                    self.log_message("已终止当前Abaqus进程", "warning")
                except Exception as e:
                    self.log_message(f"终止进程时出错: {e}", "error")
    
    def run_jobs(self):
        """运行任务队列"""
        try:
            while self.current_job_index < len(self.job_queue) and not self.should_terminate:
                if self.should_stop:
                    # 如果是停止当前任务，重置标志继续下一个
                    if not self.should_terminate:
                        self.should_stop = False
                        self.log_message("继续执行下一个任务...", "info")
                    else:
                        break
                
                job_info = self.job_queue[self.current_job_index]
                job_name = job_info['job_name']
                inp_path = job_info['path']
                
                self.log_message(f"\n{'='*60}", "info")
                self.log_message(f"任务 [{self.current_job_index + 1}/{len(self.job_queue)}]: {job_info['name']}", "info")
                self.log_message(f"{'='*60}", "info")
                
                # 清理旧文件
                self.clean_old_files(job_name)
                
                # 提交Abaqus任务
                success = self.submit_abaqus_job(inp_path, job_name)
                
                if self.should_terminate:
                    self.log_message(f"任务已终止: {job_info['name']}", "warning")
                    break
                
                if success:
                    self.log_message(f"✓ 任务完成: {job_info['name']}", "success")
                else:
                    if not self.should_stop:
                        self.log_message(f"✗ 任务中断或失败: {job_info['name']}，继续下一个任务", "error")
                    else:
                        self.log_message(f"⚠ 任务被停止: {job_info['name']}", "warning")
                
                self.current_job_index += 1
                
                # 短暂延迟
                time.sleep(1)

            if self.should_terminate:
                self.log_message("\n" + "=" * 60, "warning")
                self.log_message("所有任务已被用户终止！", "warning")
                self.log_message("=" * 60, "warning")
                messagebox.showinfo("已终止", "所有任务已被终止！")
            elif self.should_stop and not self.should_terminate:
                self.log_message("\n任务已被用户停止，已跳过的任务不再执行", "warning")
            else:
                self.log_message(f"\n{'='*60}", "info")
                self.log_message("所有任务已完成！", "success")
                self.log_message(f"{'='*60}", "info")
                messagebox.showinfo("完成", "所有任务已完成！")

        except Exception as e:
            self.log_message(f"发生错误: {str(e)}", "error")
            messagebox.showerror("错误", f"任务执行出错:\n{str(e)}")

        finally:
            self.is_running = False
            self.current_process = None

    def clean_old_files(self, job_name):
        """删除与当前任务同名的旧文件（保留inp文件）"""
        if not hasattr(self, 'folder_path'):
            return

        # 需要删除的文件扩展名
        extensions_to_delete = [
            '.sta', '.dat', '.msg', '.fil', '.odb', '.lck', '.log',
            '.res', '.sel', '.sim', '.stt', '.mdl', '.prt', '.com'
        ]

        deleted_count = 0
        for ext in extensions_to_delete:
            pattern = os.path.join(self.folder_path, f"{job_name}{ext}")
            files = glob.glob(pattern)
            for file_path in files:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    self.log_message(f"警告: 无法删除文件 {os.path.basename(file_path)}: {e}", "warning")

        if deleted_count > 0:
            self.log_message(f"已清理 {deleted_count} 个旧文件", "info")

    def submit_abaqus_job(self, inp_path, job_name):
        """提交单个Abaqus任务"""
        try:
            # 构建Abaqus命令（参考bat格式：abq2024 job=Job名 cpus=核数 int ask=off）
            cmd_str = f'{self.abaqus_cmd} job={job_name} cpus={self.cpu_count} int ask=off'

            self.log_message(f"正在提交任务: {job_name} (使用 {self.cpu_count} 个CPU核心)", "info")
            self.log_message(f"命令: {cmd_str}", "info")

            # 切换到工作目录
            original_dir = os.getcwd()
            os.chdir(self.folder_path)

            # 使用cmd /c执行命令（参考bat文件格式）
            self.current_process = subprocess.Popen(
                f'cmd /c {cmd_str}',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=True
            )

            # 监控sta文件
            sta_file = os.path.join(self.folder_path, f"{job_name}.sta")
            sta_monitor_thread = threading.Thread(
                target=self.monitor_sta_file,
                args=(sta_file, job_name)
            )
            sta_monitor_thread.daemon = True
            sta_monitor_thread.start()

            # 等待进程完成
            return_code = self.current_process.wait()

            # 恢复工作目录
            os.chdir(original_dir)

            # 清除当前进程引用
            self.current_process = None

            if return_code == 0:
                return True
            else:
                self.log_message(f"Abaqus返回错误码: {return_code}", "error")
                return False

        except FileNotFoundError:
            self.log_message("错误: 找不到Abaqus命令，请确认Abaqus已正确安装并添加到系统PATH", "error")
            self.current_process = None
            return False
        except Exception as e:
            self.log_message(f"提交任务失败: {str(e)}", "error")
            self.current_process = None
            return False

    def monitor_sta_file(self, sta_file, job_name):
        """监控sta文件并显示最后一行"""
        last_line_shown = ""

        while not os.path.exists(sta_file):
            time.sleep(0.5)
            if self.should_stop or self.should_terminate:
                return

        self.log_message(f"检测到STA文件生成: {job_name}.sta", "info")

        # 持续读取sta文件
        while True:
            try:
                if os.path.exists(sta_file):
                    with open(sta_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        if lines:
                            last_line = lines[-1].strip()
                            if last_line and last_line != last_line_shown:
                                last_line_shown = last_line
                                self.log_message(f"STA状态: {last_line}", "info")

                # 检查任务是否完成
                if self.is_job_completed(job_name):
                    break

                # 检查是否应该停止
                if self.should_stop or self.should_terminate:
                    break

                time.sleep(1)

            except Exception as e:
                time.sleep(1)

    def is_job_completed(self, job_name):
        """检查任务是否完成"""
        # 检查是否存在.sta文件并包含完成标识
        sta_file = os.path.join(self.folder_path, f"{job_name}.sta")

        if os.path.exists(sta_file):
            try:
                with open(sta_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().upper()
                    # Abaqus完成标识
                    if 'THE ANALYSIS HAS BEEN COMPLETED' in content or \
                       'ANALYSIS COMPLETE' in content or \
                       'JOB COMPLETED' in content:
                        return True
            except:
                pass

        return False


def main():
    root = tk.Tk()
    app = AbaqusJobSubmitter(root)
    root.mainloop()


if __name__ == "__main__":
    main()

