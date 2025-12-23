import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import psutil
import platform
from datetime import datetime
import subprocess
import os
from collections import deque
import csv
import json
import threading

class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("GUI Based Task Manager")
        self.root.geometry("1300x850")
        self.root.configure(bg='#1e1e1e')
        
        # Dark theme colors
        self.bg_dark = '#1e1e1e'
        self.bg_darker = '#2d2d30'
        self.bg_darkest = '#252526'
        self.fg_light = '#e0e0e0'
        self.fg_dim = '#969696'
        self.accent = '#007acc'
        self.accent_hover = '#1f87d8'
        self.critical_bg = '#5a1d1d'
        self.high_bg = '#5a4a1d'
        self.success = '#0e8a16'
        self.danger = '#d73a49'
        self.warning = '#f39c12'
        
        self.sort_column = "PID"
        self.sort_reverse = False
        
        # Historical data for graphs (60 data points = last 2 minutes at 2s intervals)
        self.cpu_history = deque([0] * 60, maxlen=60)
        self.memory_history = deque([0] * 60, maxlen=60)
        self.disk_history = deque([0] * 60, maxlen=60)
        self.network_history = deque([0] * 60, maxlen=60)
        
        # Network and disk tracking
        self.last_net_io = psutil.net_io_counters()
        self.last_disk_io = psutil.disk_io_counters()
        self.last_time = time.time()
        
        # Alert thresholds
        self.cpu_threshold = 80
        self.memory_threshold = 85
        
        # NEW FEATURES: Process monitoring and automation
        self.watched_processes = {}  # PID: {name, alerts, start_time}
        self.process_history = []  # Historical process data
        self.auto_kill_rules = []  # Rules for automatic process termination
        self.process_snapshots = []  # Saved system states
        self.alert_log = []  # Log of all alerts
        
        # Create notebook for tabs
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure notebook style
        style.configure('TNotebook', background=self.bg_dark, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.bg_darker, foreground=self.fg_light, 
                       padding=[20, 10], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', self.bg_darkest)], 
                 foreground=[('selected', self.accent)])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create all tabs
        self.create_processes_tab()
        self.create_performance_tab()
        self.create_system_info_tab()
        self.create_startup_tab()
        
        # NEW FEATURE TABS
        try:
            self.create_process_monitor_tab()
            print("✓ Process Monitor tab created")
        except Exception as e:
            print(f"Error creating Monitor tab: {e}")
        
        try:
            self.create_automation_tab()
            print("✓ Automation tab created")
        except Exception as e:
            print(f"Error creating Automation tab: {e}")
        
        try:
            self.create_history_tab()
            print("✓ History tab created")
        except Exception as e:
            print(f"Error creating History tab: {e}")
        
        try:
            self.create_alerts_tab()
            print("✓ Alerts tab created")
        except Exception as e:
            print(f"Error creating Alerts tab: {e}")
        
        self.update_data()
        
    def create_processes_tab(self):
        processes_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(processes_frame, text='Processes')
        
        # Top info bar
        info_frame = tk.Frame(processes_frame, bg=self.bg_darkest, pady=10)
        info_frame.pack(fill=tk.X)
        
        self.cpu_label = tk.Label(info_frame, text="CPU: 0%", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.cpu_label.pack(side=tk.LEFT, padx=15)
        
        self.memory_label = tk.Label(info_frame, text="Memory: 0%", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.memory_label.pack(side=tk.LEFT, padx=15)
        
        self.process_label = tk.Label(info_frame, text="Processes: 0", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.process_label.pack(side=tk.LEFT, padx=15)
        
        self.disk_label = tk.Label(info_frame, text="Disk: 0 MB/s", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.disk_label.pack(side=tk.LEFT, padx=15)
        
        self.network_label = tk.Label(info_frame, text="Network: 0 KB/s", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.network_label.pack(side=tk.LEFT, padx=15)
        
        # Process list frame
        list_frame = tk.Frame(processes_frame, bg=self.bg_dark)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        hsb = ttk.Scrollbar(list_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        columns = ("PID", "Name", "Status", "CPU%", "Memory%", "MemoryMB", "Threads", "User", "Runtime")
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        for col in columns:
            self.tree.heading(col, text=col.replace("_", " "), command=lambda c=col: self.sort_by(c))
        
        self.tree.column("PID", width=60, anchor=tk.CENTER)
        self.tree.column("Name", width=200, anchor=tk.W)
        self.tree.column("Status", width=80, anchor=tk.CENTER)
        self.tree.column("CPU%", width=70, anchor=tk.CENTER)
        self.tree.column("Memory%", width=90, anchor=tk.CENTER)
        self.tree.column("MemoryMB", width=100, anchor=tk.CENTER)
        self.tree.column("Threads", width=70, anchor=tk.CENTER)
        self.tree.column("User", width=120, anchor=tk.W)
        self.tree.column("Runtime", width=100, anchor=tk.CENTER)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        self.tree.bind('<Button-1>', self.on_tree_select)
        self.tree.bind('<<TreeviewSelect>>', self.on_selection_changed)
        self.tree.bind('<Double-Button-1>', self.on_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)
        self.tree.bind('<Return>', lambda e: self.show_details())
        self.tree.bind('<Delete>', lambda e: self.end_task())
        
        self.selected_process = None
        
        # Create context menu with NEW options
        self.context_menu = tk.Menu(self.tree, tearoff=0, bg=self.bg_darker, fg=self.fg_light,
                                    activebackground=self.accent, activeforeground='white')
        self.context_menu.add_command(label="End Task", command=self.end_task)
        self.context_menu.add_command(label="Show Details", command=self.show_details)
        self.context_menu.add_command(label="Open File Location", command=self.open_file_location)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Watch This Process", command=self.watch_process)
        self.context_menu.add_command(label="Suspend Process", command=self.suspend_process)
        self.context_menu.add_command(label="Resume Process", command=self.resume_process)
        self.context_menu.add_command(label="Change Priority", command=self.change_priority)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Refresh List", command=self.refresh_data)
        
        # Color coding tags
        self.tree.tag_configure('critical', background=self.critical_bg, foreground=self.fg_light)
        self.tree.tag_configure('high', background=self.high_bg, foreground=self.fg_light)
        self.tree.tag_configure('watched', background='#1d3a5a', foreground='#66d9ef')  # NEW
        
        # Styling
        style = ttk.Style()
        style.configure("Treeview", background=self.bg_darker, foreground=self.fg_light, 
                       fieldbackground=self.bg_darker, borderwidth=0, rowheight=25)
        style.configure("Treeview.Heading", background=self.bg_darkest, foreground=self.accent, 
                       font=('Arial', 10, 'bold'), borderwidth=1, relief='flat')
        # Subtle selection highlighting - dark gray instead of bright blue
        style.map('Treeview', 
                 background=[('selected', '#3a3a3a'), ('active', '#404040'), ('!focus', '#3a3a3a')], 
                 foreground=[('selected', self.fg_light), ('active', self.fg_light), ('!focus', self.fg_light)])
        
        # Button frame with NEW features
        button_frame = tk.Frame(processes_frame, bg=self.bg_dark, pady=10)
        button_frame.pack(fill=tk.X)
        
        btn_style = {'font': ('Arial', 10, 'bold'), 'width': 14, 'fg': 'white', 
                    'relief': tk.FLAT, 'cursor': 'hand2'}
        
        self.selected_label = tk.Label(button_frame, text="No process selected", 
                                      bg=self.bg_dark, fg=self.fg_dim, font=('Arial', 9))
        self.selected_label.pack(side=tk.LEFT, padx=10)
        
        end_btn = tk.Button(button_frame, text="End Task", command=self.end_task, bg=self.danger, 
                           activebackground='#b02a37', **btn_style)
        end_btn.pack(side=tk.LEFT, padx=5)
        
        details_btn = tk.Button(button_frame, text="Details", command=self.show_details, bg=self.accent,
                               activebackground=self.accent_hover, **btn_style)
        details_btn.pack(side=tk.LEFT, padx=5)
        
        watch_btn = tk.Button(button_frame, text="Watch", command=self.watch_process, bg='#2ecc71',
                             activebackground='#27ae60', **btn_style)
        watch_btn.pack(side=tk.LEFT, padx=5)
        
        suspend_btn = tk.Button(button_frame, text="Suspend", command=self.suspend_process, bg=self.warning,
                               activebackground='#e08e0b', **btn_style)
        suspend_btn.pack(side=tk.LEFT, padx=5)
        
        resume_btn = tk.Button(button_frame, text="Resume", command=self.resume_process, bg='#9b59b6',
                              activebackground='#8e44ad', **btn_style)
        resume_btn.pack(side=tk.LEFT, padx=5)
        
        priority_btn = tk.Button(button_frame, text="Priority", command=self.change_priority, bg='#34495e',
                                activebackground='#2c3e50', **btn_style)
        priority_btn.pack(side=tk.LEFT, padx=5)
        
        snapshot_btn = tk.Button(button_frame, text="Snapshot", command=self.take_snapshot, bg=self.success,
                                activebackground='#12a11d', **btn_style)
        snapshot_btn.pack(side=tk.LEFT, padx=5)
        
        export_btn = tk.Button(button_frame, text="Export CSV", command=self.export_data, bg=self.accent,
                              activebackground=self.accent_hover, **btn_style)
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # Search frame
        search_frame = tk.Frame(button_frame, bg=self.bg_dark)
        search_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(search_frame, text="Search:", bg=self.bg_dark, fg=self.fg_light, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_processes)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=20, font=('Arial', 10),
                               bg=self.bg_darker, fg=self.fg_light, insertbackground=self.fg_light, 
                               relief=tk.FLAT, borderwidth=2)
        search_entry.pack(side=tk.LEFT)
        
    def create_performance_tab(self):
        perf_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(perf_frame, text='Performance')
        
        self.perf_canvas = tk.Canvas(perf_frame, bg=self.bg_darker, highlightthickness=0)
        self.perf_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        perf_info_frame = tk.Frame(perf_frame, bg=self.bg_darkest, pady=10)
        perf_info_frame.pack(fill=tk.X)
        
        self.perf_cpu_label = tk.Label(perf_info_frame, text="CPU: 0%", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.perf_cpu_label.pack(side=tk.LEFT, padx=20)
        
        self.perf_mem_label = tk.Label(perf_info_frame, text="Memory: 0 GB / 0 GB", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.perf_mem_label.pack(side=tk.LEFT, padx=20)
        
        self.perf_disk_label = tk.Label(perf_info_frame, text="Disk: 0 MB/s", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.perf_disk_label.pack(side=tk.LEFT, padx=20)
        
        self.perf_net_label = tk.Label(perf_info_frame, text="Network: ↑0 KB/s ↓0 KB/s", bg=self.bg_darkest, fg=self.fg_light, font=('Arial', 11, 'bold'))
        self.perf_net_label.pack(side=tk.LEFT, padx=20)
        
    def create_system_info_tab(self):
        info_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(info_frame, text='System Info')
        
        text_frame = tk.Frame(info_frame, bg=self.bg_dark)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sys_info_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10), 
                                     yscrollcommand=scrollbar.set, bg=self.bg_darker, 
                                     fg=self.fg_light, insertbackground=self.fg_light, 
                                     selectbackground=self.accent, relief=tk.FLAT, padx=10, pady=10)
        self.sys_info_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.sys_info_text.yview)
        
        self.update_system_info()
        
    def create_startup_tab(self):
        startup_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(startup_frame, text='Startup Programs')
        
        tk.Label(startup_frame, text="Startup Programs", bg=self.bg_dark, fg=self.fg_light, 
                font=('Arial', 11, 'bold'), pady=15).pack()
        
        list_frame = tk.Frame(startup_frame, bg=self.bg_dark)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Name", "Publisher", "Status", "Location")
        self.startup_tree = ttk.Treeview(list_frame, columns=columns, show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self.startup_tree.yview)
        
        for col in columns:
            self.startup_tree.heading(col, text=col)
        
        self.startup_tree.column("Name", width=200)
        self.startup_tree.column("Publisher", width=150)
        self.startup_tree.column("Status", width=100)
        self.startup_tree.column("Location", width=350)
        
        self.startup_tree.pack(fill=tk.BOTH, expand=True)
        
        self.load_startup_items()
        
        btn_frame = tk.Frame(startup_frame, bg=self.bg_dark, pady=10)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="Refresh", font=('Arial', 10, 'bold'), width=12, bg=self.accent, 
                 fg='white', relief=tk.FLAT, cursor='hand2', activebackground=self.accent_hover,
                 command=self.load_startup_items).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Enable", font=('Arial', 10, 'bold'), width=12, bg=self.success, 
                 fg='white', relief=tk.FLAT, cursor='hand2', activebackground='#12a11d',
                 command=self.enable_startup).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Disable", font=('Arial', 10, 'bold'), width=12, bg=self.danger, 
                 fg='white', relief=tk.FLAT, cursor='hand2', activebackground='#b02a37',
                 command=self.disable_startup).pack(side=tk.LEFT, padx=10)
    
    # NEW FEATURE: Process Monitor Tab
    def create_process_monitor_tab(self):
        monitor_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(monitor_frame, text='🔍 Monitor')
        
        tk.Label(monitor_frame, text="Watched Processes", bg=self.bg_dark, fg=self.fg_light,
                font=('Arial', 12, 'bold'), pady=15).pack()
        
        list_frame = tk.Frame(monitor_frame, bg=self.bg_dark)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("PID", "Name", "CPU%", "Memory%", "Runtime", "Status", "Alerts")
        self.monitor_tree = ttk.Treeview(list_frame, columns=columns, show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self.monitor_tree.yview)
        
        for col in columns:
            self.monitor_tree.heading(col, text=col)
        
        self.monitor_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(monitor_frame, bg=self.bg_dark, pady=10)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="Stop Watching", font=('Arial', 10, 'bold'), width=15, bg=self.danger,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.stop_watching_selected).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Clear All", font=('Arial', 10, 'bold'), width=15, bg=self.accent,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.clear_watched).pack(side=tk.LEFT, padx=10)
    
    # NEW FEATURE: Automation Tab
    def create_automation_tab(self):
        auto_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(auto_frame, text='⚡ Auto-Kill')
        
        tk.Label(auto_frame, text="Automatic Process Termination Rules", bg=self.bg_dark, fg=self.fg_light,
                font=('Arial', 12, 'bold'), pady=15).pack()
        
        # Rule creation frame
        rule_frame = tk.Frame(auto_frame, bg=self.bg_darker, pady=15)
        rule_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(rule_frame, text="Process Name:", bg=self.bg_darker, fg=self.fg_light).grid(row=0, column=0, padx=5, pady=5)
        self.auto_name_entry = tk.Entry(rule_frame, width=30, bg=self.bg_darkest, fg=self.fg_light)
        self.auto_name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(rule_frame, text="CPU Threshold (%):", bg=self.bg_darker, fg=self.fg_light).grid(row=0, column=2, padx=5, pady=5)
        self.auto_cpu_entry = tk.Entry(rule_frame, width=10, bg=self.bg_darkest, fg=self.fg_light)
        self.auto_cpu_entry.insert(0, "90")
        self.auto_cpu_entry.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(rule_frame, text="Memory Threshold (%):", bg=self.bg_darker, fg=self.fg_light).grid(row=1, column=0, padx=5, pady=5)
        self.auto_mem_entry = tk.Entry(rule_frame, width=10, bg=self.bg_darkest, fg=self.fg_light)
        self.auto_mem_entry.insert(0, "90")
        self.auto_mem_entry.grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(rule_frame, text="Duration (seconds):", bg=self.bg_darker, fg=self.fg_light).grid(row=1, column=2, padx=5, pady=5)
        self.auto_duration_entry = tk.Entry(rule_frame, width=10, bg=self.bg_darkest, fg=self.fg_light)
        self.auto_duration_entry.insert(0, "10")
        self.auto_duration_entry.grid(row=1, column=3, padx=5, pady=5)
        
        tk.Button(rule_frame, text="Add Rule", font=('Arial', 10, 'bold'), width=15, bg=self.success,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.add_auto_kill_rule).grid(row=2, column=0, columnspan=4, pady=10)
        
        # Rules list
        list_frame = tk.Frame(auto_frame, bg=self.bg_dark)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Process", "CPU%", "Memory%", "Duration", "Status", "Triggers")
        self.auto_tree = ttk.Treeview(list_frame, columns=columns, show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self.auto_tree.yview)
        
        for col in columns:
            self.auto_tree.heading(col, text=col)
        
        self.auto_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(auto_frame, bg=self.bg_dark, pady=10)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="Remove Rule", font=('Arial', 10, 'bold'), width=15, bg=self.danger,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.remove_auto_rule).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Clear All Rules", font=('Arial', 10, 'bold'), width=15, bg=self.accent,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.clear_auto_rules).pack(side=tk.LEFT, padx=10)
    
    # NEW FEATURE: History Tab
    def create_history_tab(self):
        history_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(history_frame, text='📊 History')
        
        tk.Label(history_frame, text="Process History & Snapshots", bg=self.bg_dark, fg=self.fg_light,
                font=('Arial', 12, 'bold'), pady=15).pack()
        
        list_frame = tk.Frame(history_frame, bg=self.bg_dark)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Timestamp", "Processes", "CPU%", "Memory%", "Description")
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self.history_tree.yview)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(history_frame, bg=self.bg_dark, pady=10)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="View Details", font=('Arial', 10, 'bold'), width=15, bg=self.accent,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.view_snapshot_details).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Export Snapshot", font=('Arial', 10, 'bold'), width=15, bg=self.success,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.export_snapshot).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Clear History", font=('Arial', 10, 'bold'), width=15, bg=self.danger,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.clear_history).pack(side=tk.LEFT, padx=10)
    
    # NEW FEATURE: Alerts Tab
    def create_alerts_tab(self):
        alerts_frame = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(alerts_frame, text='🔔 Alerts')
        
        tk.Label(alerts_frame, text="System Alerts & Notifications", bg=self.bg_dark, fg=self.fg_light,
                font=('Arial', 12, 'bold'), pady=15).pack()
        
        text_frame = tk.Frame(alerts_frame, bg=self.bg_dark)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.alerts_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10),
                                   yscrollcommand=scrollbar.set, bg=self.bg_darker,
                                   fg=self.fg_light, insertbackground=self.fg_light,
                                   selectbackground=self.accent, relief=tk.FLAT, padx=10, pady=10)
        self.alerts_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.alerts_text.yview)
        
        btn_frame = tk.Frame(alerts_frame, bg=self.bg_dark, pady=10)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="Clear Alerts", font=('Arial', 10, 'bold'), width=15, bg=self.danger,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.clear_alerts).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Export Log", font=('Arial', 10, 'bold'), width=15, bg=self.accent,
                 fg='white', relief=tk.FLAT, cursor='hand2',
                 command=self.export_alerts).pack(side=tk.LEFT, padx=10)
    
    # NEW FEATURE METHODS
    
    def watch_process(self):
        """Add process to watch list"""
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
            name = self.selected_process['name']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process to watch")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
            name = values[1]
        
        if pid in self.watched_processes:
            messagebox.showinfo("Info", f"Process '{name}' is already being watched")
            return
        
        try:
            proc = psutil.Process(pid)
            self.watched_processes[pid] = {
                'name': name,
                'start_time': datetime.now(),
                'alerts': 0,
                'max_cpu': 0,
                'max_memory': 0
            }
            self.add_alert(f"Started watching process: {name} (PID: {pid})")
            messagebox.showinfo("Success", f"Now watching process: {name}")
            self.update_monitor_display()
        except psutil.NoSuchProcess:
            messagebox.showerror("Error", "Process no longer exists")
    
    def stop_watching_selected(self):
        """Stop watching selected process"""
        selected = self.monitor_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a process to stop watching")
            return
        
        values = self.monitor_tree.item(selected[0])['values']
        pid = int(values[0])
        
        if pid in self.watched_processes:
            name = self.watched_processes[pid]['name']
            del self.watched_processes[pid]
            self.add_alert(f"Stopped watching process: {name} (PID: {pid})")
            self.update_monitor_display()
            messagebox.showinfo("Success", f"Stopped watching process")
    
    def clear_watched(self):
        """Clear all watched processes"""
        if self.watched_processes and messagebox.askyesno("Confirm", "Clear all watched processes?"):
            self.watched_processes.clear()
            self.update_monitor_display()
            self.add_alert("Cleared all watched processes")
    
    def suspend_process(self):
        """Suspend a process"""
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
            name = self.selected_process['name']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process to suspend")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
            name = values[1]
        
        if messagebox.askyesno("Confirm", f"Suspend process '{name}'?\n\nThis will pause execution."):
            try:
                proc = psutil.Process(pid)
                proc.suspend()
                self.add_alert(f"Suspended process: {name} (PID: {pid})")
                messagebox.showinfo("Success", f"Process '{name}' suspended")
            except psutil.AccessDenied:
                messagebox.showerror("Error", "Access denied. Try running as administrator.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def resume_process(self):
        """Resume a suspended process"""
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
            name = self.selected_process['name']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process to resume")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
            name = values[1]
        
        try:
            proc = psutil.Process(pid)
            proc.resume()
            self.add_alert(f"Resumed process: {name} (PID: {pid})")
            messagebox.showinfo("Success", f"Process '{name}' resumed")
        except psutil.AccessDenied:
            messagebox.showerror("Error", "Access denied. Try running as administrator.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def change_priority(self):
        """Change process priority"""
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
            name = self.selected_process['name']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
            name = values[1]
        
        # Create priority selection dialog
        priority_window = tk.Toplevel(self.root)
        priority_window.title(f"Change Priority - {name}")
        priority_window.geometry("350x250")
        priority_window.configure(bg=self.bg_dark)
        
        tk.Label(priority_window, text=f"Change priority for {name}:", bg=self.bg_dark,
                fg=self.fg_light, font=('Arial', 11, 'bold')).pack(pady=15)
        
        priorities = {
            "Realtime": psutil.REALTIME_PRIORITY_CLASS if platform.system() == 'Windows' else -20,
            "High": psutil.HIGH_PRIORITY_CLASS if platform.system() == 'Windows' else -10,
            "Above Normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS if platform.system() == 'Windows' else -5,
            "Normal": psutil.NORMAL_PRIORITY_CLASS if platform.system() == 'Windows' else 0,
            "Below Normal": psutil.BELOW_NORMAL_PRIORITY_CLASS if platform.system() == 'Windows' else 5,
            "Low": psutil.IDLE_PRIORITY_CLASS if platform.system() == 'Windows' else 19
        }
        
        selected_priority = tk.StringVar(value="Normal")
        
        for pname in priorities.keys():
            tk.Radiobutton(priority_window, text=pname, variable=selected_priority, value=pname,
                          bg=self.bg_dark, fg=self.fg_light, selectcolor=self.bg_darker,
                          activebackground=self.bg_dark, activeforeground=self.accent,
                          font=('Arial', 10)).pack(anchor=tk.W, padx=30, pady=3)
        
        def apply_priority():
            try:
                proc = psutil.Process(pid)
                priority_value = priorities[selected_priority.get()]
                if platform.system() == 'Windows':
                    proc.nice(priority_value)
                else:
                    import os
                    os.setpriority(os.PRIO_PROCESS, pid, priority_value)
                self.add_alert(f"Changed priority of {name} to {selected_priority.get()}")
                messagebox.showinfo("Success", f"Priority changed to {selected_priority.get()}")
                priority_window.destroy()
            except psutil.AccessDenied:
                messagebox.showerror("Error", "Access denied. Try running as administrator.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {str(e)}")
        
        tk.Button(priority_window, text="Apply", command=apply_priority, font=('Arial', 10, 'bold'),
                 bg=self.accent, fg='white', relief=tk.FLAT, width=12).pack(pady=10)
    
    def take_snapshot(self):
        """Take a snapshot of current system state"""
        snapshot = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'processes': [],
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'description': f"Snapshot at {datetime.now().strftime('%H:%M:%S')}"
        }
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                snapshot['processes'].append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu': proc.info['cpu_percent'] or 0,
                    'memory': proc.info['memory_percent'] or 0
                })
            except:
                pass
        
        self.process_snapshots.append(snapshot)
        self.update_history_display()
        self.add_alert(f"Snapshot taken: {len(snapshot['processes'])} processes captured")
        messagebox.showinfo("Success", f"Snapshot saved with {len(snapshot['processes'])} processes")
    
    def add_auto_kill_rule(self):
        """Add automatic process termination rule"""
        name = self.auto_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Enter a process name")
            return
        
        try:
            cpu_threshold = float(self.auto_cpu_entry.get())
            mem_threshold = float(self.auto_mem_entry.get())
            duration = int(self.auto_duration_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid threshold values")
            return
        
        rule = {
            'name': name,
            'cpu_threshold': cpu_threshold,
            'mem_threshold': mem_threshold,
            'duration': duration,
            'triggers': 0,
            'active': True,
            'last_trigger': None
        }
        
        self.auto_kill_rules.append(rule)
        self.update_auto_display()
        self.add_alert(f"Auto-kill rule added: {name} (CPU>{cpu_threshold}% OR Mem>{mem_threshold}% for {duration}s)")
        messagebox.showinfo("Success", f"Auto-kill rule added for '{name}'")
    
    def remove_auto_rule(self):
        """Remove selected auto-kill rule"""
        selected = self.auto_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a rule to remove")
            return
        
        values = self.auto_tree.item(selected[0])['values']
        process_name = values[0]
        
        self.auto_kill_rules = [r for r in self.auto_kill_rules if r['name'] != process_name]
        self.update_auto_display()
        self.add_alert(f"Removed auto-kill rule for: {process_name}")
    
    def clear_auto_rules(self):
        """Clear all auto-kill rules"""
        if self.auto_kill_rules and messagebox.askyesno("Confirm", "Clear all auto-kill rules?"):
            self.auto_kill_rules.clear()
            self.update_auto_display()
            self.add_alert("Cleared all auto-kill rules")
    
    def add_alert(self, message):
        """Add alert to alert log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_entry = f"[{timestamp}] {message}"
        self.alert_log.append(alert_entry)
        
        # Keep only last 1000 alerts
        if len(self.alert_log) > 1000:
            self.alert_log = self.alert_log[-1000:]
        
        self.update_alerts_display()
    
    def update_monitor_display(self):
        """Update the watched processes display"""
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        
        for pid, data in list(self.watched_processes.items()):
            try:
                proc = psutil.Process(pid)
                cpu = proc.cpu_percent()
                mem = proc.memory_percent()
                runtime = datetime.now() - data['start_time']
                runtime_str = f"{runtime.seconds//3600}h {(runtime.seconds//60)%60}m"
                
                # Update max values
                data['max_cpu'] = max(data['max_cpu'], cpu)
                data['max_memory'] = max(data['max_memory'], mem)
                
                self.monitor_tree.insert('', tk.END, values=(
                    pid, data['name'], f"{cpu:.1f}%", f"{mem:.2f}%",
                    runtime_str, proc.status(), data['alerts']
                ))
            except psutil.NoSuchProcess:
                # Process ended, remove from watch list
                self.add_alert(f"Watched process ended: {data['name']} (PID: {pid})")
                del self.watched_processes[pid]
    
    def update_auto_display(self):
        """Update auto-kill rules display"""
        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)
        
        for rule in self.auto_kill_rules:
            status = "Active" if rule['active'] else "Inactive"
            self.auto_tree.insert('', tk.END, values=(
                rule['name'], f"{rule['cpu_threshold']}%", f"{rule['mem_threshold']}%",
                f"{rule['duration']}s", status, rule['triggers']
            ))
    
    def update_history_display(self):
        """Update history/snapshots display"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        for snapshot in self.process_snapshots[-50:]:  # Show last 50 snapshots
            self.history_tree.insert('', tk.END, values=(
                snapshot['timestamp'],
                len(snapshot['processes']),
                f"{snapshot['cpu']:.1f}%",
                f"{snapshot['memory']:.1f}%",
                snapshot['description']
            ))
    
    def update_alerts_display(self):
        """Update alerts text display"""
        self.alerts_text.delete(1.0, tk.END)
        
        # Show last 100 alerts
        for alert in self.alert_log[-100:]:
            self.alerts_text.insert(tk.END, alert + "\n")
        
        self.alerts_text.see(tk.END)
    
    def check_auto_kill_rules(self):
        """Check and execute auto-kill rules"""
        for rule in self.auto_kill_rules:
            if not rule['active']:
                continue
            
            for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                try:
                    if proc.info['name'].lower() == rule['name'].lower():
                        cpu = proc.info['cpu_percent'] or 0
                        mem = proc.info['memory_percent'] or 0
                        
                        if cpu > rule['cpu_threshold'] or mem > rule['mem_threshold']:
                            # Would need to track duration properly - simplified here
                            rule['triggers'] += 1
                            self.add_alert(f"⚠ Auto-kill triggered: {rule['name']} (CPU:{cpu:.1f}% MEM:{mem:.1f}%)")
                            
                            # Kill the process
                            try:
                                proc.terminate()
                                self.add_alert(f"✓ Auto-killed process: {rule['name']}")
                            except:
                                pass
                except:
                    pass
    
    def view_snapshot_details(self):
        """View details of selected snapshot"""
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a snapshot to view")
            return
        
        values = self.history_tree.item(selected[0])['values']
        timestamp = values[0]
        
        # Find the snapshot
        snapshot = None
        for s in self.process_snapshots:
            if s['timestamp'] == timestamp:
                snapshot = s
                break
        
        if not snapshot:
            messagebox.showerror("Error", "Snapshot not found")
            return
        
        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Snapshot Details - {timestamp}")
        detail_window.geometry("700x500")
        detail_window.configure(bg=self.bg_dark)
        
        text_widget = tk.Text(detail_window, wrap=tk.WORD, font=('Consolas', 9),
                             bg=self.bg_darker, fg=self.fg_light)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Format snapshot data
        details = f"""
SNAPSHOT DETAILS
================
Time: {snapshot['timestamp']}
Total Processes: {len(snapshot['processes'])}
System CPU: {snapshot['cpu']:.1f}%
System Memory: {snapshot['memory']:.1f}%

TOP PROCESSES BY CPU:
---------------------
"""
        top_cpu = sorted(snapshot['processes'], key=lambda x: x['cpu'], reverse=True)[:10]
        for proc in top_cpu:
            details += f"{proc['name']:<30} PID:{proc['pid']:<8} CPU:{proc['cpu']:.1f}%  MEM:{proc['memory']:.2f}%\n"
        
        details += "\nTOP PROCESSES BY MEMORY:\n---------------------\n"
        top_mem = sorted(snapshot['processes'], key=lambda x: x['memory'], reverse=True)[:10]
        for proc in top_mem:
            details += f"{proc['name']:<30} PID:{proc['pid']:<8} CPU:{proc['cpu']:.1f}%  MEM:{proc['memory']:.2f}%\n"
        
        text_widget.insert(1.0, details)
        text_widget.config(state=tk.DISABLED)
    
    def export_snapshot(self):
        """Export selected snapshot to JSON"""
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a snapshot to export")
            return
        
        values = self.history_tree.item(selected[0])['values']
        timestamp = values[0]
        
        snapshot = None
        for s in self.process_snapshots:
            if s['timestamp'] == timestamp:
                snapshot = s
                break
        
        if not snapshot:
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"snapshot_{timestamp.replace(':', '-')}.json"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(snapshot, f, indent=2)
                messagebox.showinfo("Success", f"Snapshot exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    # ORIGINAL METHODS (preserved from your code)
    
    def load_startup_items(self):
        """Load startup items from Windows registry and startup folders"""
        for item in self.startup_tree.get_children():
            self.startup_tree.delete(item)
        
        startup_items = []
        
        if platform.system() == 'Windows':
            try:
                import winreg
                
                reg_paths = [
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                ]
                
                for hkey, path in reg_paths:
                    try:
                        key = winreg.OpenKey(hkey, path, 0, winreg.KEY_READ)
                        i = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(key, i)
                                location = "Registry: " + ("HKCU" if hkey == winreg.HKEY_CURRENT_USER else "HKLM")
                                startup_items.append((name, "Unknown", "Enabled", value, hkey, path))
                                i += 1
                            except WindowsError:
                                break
                        winreg.CloseKey(key)
                    except:
                        pass
                
                startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
                if os.path.exists(startup_folder):
                    for file in os.listdir(startup_folder):
                        full_path = os.path.join(startup_folder, file)
                        startup_items.append((file, "Unknown", "Enabled", full_path, None, None))
                
            except ImportError:
                startup_items.append(("Error", "winreg module not available", "N/A", "N/A", None, None))
        else:
            startup_items.append(("Info", "Startup management is Windows-only", "N/A", "N/A", None, None))
        
        for item in startup_items:
            self.startup_tree.insert('', tk.END, values=item[:4], tags=('startup',))
    
    def enable_startup(self):
        selected = self.startup_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a startup item to enable")
            return
        
        item = self.startup_tree.item(selected[0])
        name = item['values'][0]
        location = item['values'][3]
        
        if platform.system() != 'Windows':
            messagebox.showinfo("Info", "Startup management is only available on Windows")
            return
        
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            result = messagebox.askyesnocancel(
                "Enable Startup Item",
                f"Enable '{name}' to run at startup?\n\nThis will add it to your user startup registry."
            )
            
            if result:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                    
                    if "Registry:" not in location:
                        command = location
                    else:
                        command = messagebox.askstring("Command Path", 
                                                      "Enter the full path to the executable:")
                        if not command:
                            return
                    
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                    winreg.CloseKey(key)
                    
                    messagebox.showinfo("Success", f"'{name}' enabled in startup successfully!")
                    self.load_startup_items()
                    
                except Exception as e:
                    messagebox.showerror("Error", 
                        f"Failed to enable startup item: {str(e)}\n\nYou may need administrator privileges.")
                    
        except ImportError:
            messagebox.showerror("Error", "Windows registry module not available")
    
    def disable_startup(self):
        selected = self.startup_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a startup item to disable")
            return
        
        item = self.startup_tree.item(selected[0])
        name = item['values'][0]
        location = item['values'][3]
        
        if platform.system() != 'Windows':
            messagebox.showinfo("Info", "Startup management is only available on Windows")
            return
        
        if messagebox.askyesno("Confirm", f"Disable startup item '{name}'?"):
            try:
                import winreg
                
                if "HKCU" in location or "Registry: HKCU" in location:
                    hkey = winreg.HKEY_CURRENT_USER
                    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                elif "HKLM" in location or "Registry: HKLM" in location:
                    hkey = winreg.HKEY_LOCAL_MACHINE
                    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                else:
                    hkey = winreg.HKEY_CURRENT_USER
                    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                
                try:
                    key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_SET_VALUE)
                    try:
                        winreg.DeleteValue(key, name)
                        winreg.CloseKey(key)
                        messagebox.showinfo("Success", f"'{name}' disabled from startup!")
                        self.load_startup_items()
                    except FileNotFoundError:
                        winreg.CloseKey(key)
                        
                        if hkey == winreg.HKEY_CURRENT_USER:
                            hkey = winreg.HKEY_LOCAL_MACHINE
                        else:
                            hkey = winreg.HKEY_CURRENT_USER
                        
                        try:
                            key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_SET_VALUE)
                            winreg.DeleteValue(key, name)
                            winreg.CloseKey(key)
                            messagebox.showinfo("Success", f"'{name}' disabled from startup!")
                            self.load_startup_items()
                        except:
                            if "Startup" in location and os.path.exists(location):
                                if messagebox.askyesno("Delete File", 
                                    "This is a file in the Startup folder. Delete it?"):
                                    try:
                                        os.remove(location)
                                        messagebox.showinfo("Success", f"File deleted from startup folder!")
                                        self.load_startup_items()
                                    except Exception as e:
                                        messagebox.showerror("Error", f"Failed to delete: {str(e)}")
                            else:
                                messagebox.showerror("Error", 
                                    "Could not find this startup item in registry.\n"
                                    "It may require administrator privileges to modify.")
                
                except PermissionError:
                    messagebox.showerror("Error", 
                        "Access denied. This startup item requires administrator privileges to modify.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to disable: {str(e)}")
                    
            except ImportError:
                messagebox.showerror("Error", "Windows registry module not available")
        
    def update_system_info(self):
        self.sys_info_text.delete(1.0, tk.END)
        
        info = f"""
╔══════════════════════════════════════════════════════════════╗
║                      SYSTEM INFORMATION                      ║
╚══════════════════════════════════════════════════════════════╝

【 OPERATING SYSTEM 】
  OS: {platform.system()} {platform.release()}
  Version: {platform.version()}
  Architecture: {platform.machine()}
  Computer Name: {platform.node()}

【 PROCESSOR 】
  Processor: {platform.processor()}
  Physical Cores: {psutil.cpu_count(logical=False)}
  Logical Cores: {psutil.cpu_count(logical=True)}
  Current Frequency: {psutil.cpu_freq().current:.2f} MHz
  Max Frequency: {psutil.cpu_freq().max:.2f} MHz

【 MEMORY 】
  Total RAM: {psutil.virtual_memory().total / (1024**3):.2f} GB
  Available RAM: {psutil.virtual_memory().available / (1024**3):.2f} GB
  Used RAM: {psutil.virtual_memory().used / (1024**3):.2f} GB
  Memory Usage: {psutil.virtual_memory().percent}%

【 DISK INFORMATION 】"""
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info += f"""
  Drive: {partition.device}
    Mount Point: {partition.mountpoint}
    File System: {partition.fstype}
    Total: {usage.total / (1024**3):.2f} GB
    Used: {usage.used / (1024**3):.2f} GB
    Free: {usage.free / (1024**3):.2f} GB
    Usage: {usage.percent}%
"""
            except:
                pass
        
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        info += f"""
【 SYSTEM UPTIME 】
  Boot Time: {boot_time.strftime("%Y-%m-%d %H:%M:%S")}
  Uptime: {uptime.days} days, {uptime.seconds//3600} hours, {(uptime.seconds//60)%60} minutes

【 NETWORK 】"""
        
        net_io = psutil.net_io_counters()
        info += f"""
  Bytes Sent: {net_io.bytes_sent / (1024**3):.2f} GB
  Bytes Received: {net_io.bytes_recv / (1024**3):.2f} GB
  Packets Sent: {net_io.packets_sent}
  Packets Received: {net_io.packets_recv}
"""
        
        self.sys_info_text.insert(1.0, info)
        
    def get_processes(self):
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'num_threads', 'username', 'create_time']):
            try:
                pinfo = proc.info
                mem_mb = pinfo['memory_info'].rss / (1024 * 1024) if pinfo.get('memory_info') else 0
                username = pinfo.get('username', 'N/A')
                if username and '\\' in username:
                    username = username.split('\\')[-1]
                
                # Calculate runtime
                create_time = pinfo.get('create_time', 0)
                if create_time:
                    runtime = datetime.now() - datetime.fromtimestamp(create_time)
                    if runtime.days > 0:
                        runtime_str = f"{runtime.days}d {runtime.seconds//3600}h"
                    elif runtime.seconds >= 3600:
                        runtime_str = f"{runtime.seconds//3600}h {(runtime.seconds//60)%60}m"
                    else:
                        runtime_str = f"{runtime.seconds//60}m"
                else:
                    runtime_str = "N/A"
                
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'status': pinfo['status'],
                    'cpu': pinfo['cpu_percent'] or 0,
                    'memory': round(pinfo['memory_percent'], 2),
                    'memory_mb': round(mem_mb, 1),
                    'threads': pinfo['num_threads'],
                    'username': username,
                    'runtime': runtime_str
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return processes
    
    def update_data(self):
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        process_count = len(psutil.pids())
        
        current_net = psutil.net_io_counters()
        current_time = time.time()
        time_delta = current_time - self.last_time
        
        if time_delta > 0:
            net_sent = (current_net.bytes_sent - self.last_net_io.bytes_sent) / time_delta / 1024
            net_recv = (current_net.bytes_recv - self.last_net_io.bytes_recv) / time_delta / 1024
        else:
            net_sent = net_recv = 0
        
        self.last_net_io = current_net
        
        current_disk = psutil.disk_io_counters()
        if current_disk and time_delta > 0:
            disk_read = (current_disk.read_bytes - self.last_disk_io.read_bytes) / time_delta / (1024*1024)
            disk_write = (current_disk.write_bytes - self.last_disk_io.write_bytes) / time_delta / (1024*1024)
            disk_total = disk_read + disk_write
        else:
            disk_total = 0
        
        self.last_disk_io = current_disk if current_disk else self.last_disk_io
        self.last_time = current_time
        
        cpu_text = f"CPU: {cpu}%"
        if cpu > self.cpu_threshold:
            cpu_text += " ⚠️"
        self.cpu_label.config(text=cpu_text)
        
        mem_text = f"Memory: {memory.percent}%"
        if memory.percent > self.memory_threshold:
            mem_text += " ⚠️"
        self.memory_label.config(text=mem_text)
        
        self.process_label.config(text=f"Processes: {process_count}")
        self.disk_label.config(text=f"Disk: {disk_total:.1f} MB/s")
        self.network_label.config(text=f"Network: ↑{net_sent:.1f} ↓{net_recv:.1f} KB/s")
        
        self.perf_cpu_label.config(text=f"CPU: {cpu}%")
        mem_used_gb = memory.used / (1024**3)
        mem_total_gb = memory.total / (1024**3)
        self.perf_mem_label.config(text=f"Memory: {mem_used_gb:.1f} GB / {mem_total_gb:.1f} GB ({memory.percent}%)")
        self.perf_disk_label.config(text=f"Disk: {disk_total:.1f} MB/s")
        self.perf_net_label.config(text=f"Network: ↑{net_sent:.1f} KB/s ↓{net_recv:.1f} KB/s")
        
        self.cpu_history.append(cpu)
        self.memory_history.append(memory.percent)
        self.disk_history.append(disk_total)
        self.network_history.append((net_sent + net_recv) / 2)
        
        self.draw_performance_graphs()
        self.refresh_data()
        
        # Update new features
        self.update_monitor_display()
        self.check_auto_kill_rules()
        
        self.root.after(2000, self.update_data)
    
    def draw_performance_graphs(self):
        self.perf_canvas.delete("all")
        width = self.perf_canvas.winfo_width()
        height = self.perf_canvas.winfo_height()
        
        if width < 10 or height < 10:
            return
        
        graph_width = (width - 60) // 2
        graph_height = (height - 60) // 2
        padding = 20
        
        self.draw_graph(padding, padding, graph_width, graph_height, 
                       list(self.cpu_history), "CPU Usage (%)", "#e74c3c", 100)
        
        self.draw_graph(padding + graph_width + 20, padding, graph_width, graph_height,
                       list(self.memory_history), "Memory Usage (%)", "#3498db", 100)
        
        max_disk = max(self.disk_history) if max(self.disk_history) > 0 else 1
        self.draw_graph(padding, padding + graph_height + 20, graph_width, graph_height,
                       list(self.disk_history), "Disk Activity (MB/s)", "#2ecc71", max_disk * 1.2)
        
        max_net = max(self.network_history) if max(self.network_history) > 0 else 1
        self.draw_graph(padding + graph_width + 20, padding + graph_height + 20, 
                       graph_width, graph_height, list(self.network_history), 
                       "Network Activity (KB/s)", "#f39c12", max_net * 1.2)
    
    def draw_graph(self, x, y, width, height, data, title, color, max_val):
        self.perf_canvas.create_rectangle(x, y, x + width, y + height, fill=self.bg_darkest, 
                                         outline=self.bg_darker, width=2)
        
        self.perf_canvas.create_text(x + width//2, y + 15, text=title, font=('Arial', 11, 'bold'), 
                                     fill=self.fg_light)
        
        current = data[-1] if data else 0
        self.perf_canvas.create_text(x + width//2, y + height - 15, text=f"{current:.1f}", 
                                     font=('Arial', 10, 'bold'), fill=color)
        
        for i in range(5):
            y_pos = y + 30 + (height - 60) * i / 4
            self.perf_canvas.create_line(x + 10, y_pos, x + width - 10, y_pos, fill='#3e3e42', dash=(2, 2))
        
        if len(data) > 1:
            points = []
            for i, value in enumerate(data):
                px = x + 10 + (width - 20) * i / (len(data) - 1)
                py = y + 30 + (height - 60) * (1 - min(value, max_val) / max_val)
                points.extend([px, py])
            
            if len(points) >= 4:
                self.perf_canvas.create_line(points, fill=color, width=2, smooth=True)
    
    def refresh_data(self):
        # Store currently selected PID before refresh
        selected_pid = None
        if self.selected_process:
            selected_pid = self.selected_process['pid']
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        processes = self.get_processes()
        search_term = self.search_var.get().lower()
        
        new_selected_item = None
        
        for proc in processes:
            if search_term == "" or search_term in proc['name'].lower():
                tags = ()
                if proc['pid'] in self.watched_processes:
                    tags = ('watched',)
                elif proc['cpu'] > 50 or proc['memory'] > 50:
                    tags = ('critical',)
                elif proc['cpu'] > 30 or proc['memory'] > 30:
                    tags = ('high',)
                
                item_id = self.tree.insert('', tk.END, values=(
                    proc['pid'], proc['name'], proc['status'],
                    f"{proc['cpu']:.1f}%", f"{proc['memory']:.2f}%",
                    f"{proc['memory_mb']:.1f} MB", proc['threads'], proc['username'], proc['runtime']
                ), tags=tags)
                
                # Re-select the previously selected process
                if selected_pid and proc['pid'] == selected_pid:
                    new_selected_item = item_id
        
        # Restore selection
        if new_selected_item:
            self.tree.selection_set(new_selected_item)
            self.tree.focus(new_selected_item)
            self.tree.see(new_selected_item)
    
    def filter_processes(self, *args):
        self.refresh_data()
    
    def on_tree_select(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            # Don't clear selection, just add to it
            self.tree.selection_set(item)
            self.tree.focus(item)
            
            try:
                values = self.tree.item(item)['values']
                if values and len(values) >= 2:
                    self.selected_process = {
                        'pid': int(values[0]),
                        'name': values[1],
                        'item_id': item
                    }
                    self.selected_label.config(
                        text=f"Selected: {values[1]} (PID: {values[0]})",
                        fg=self.accent
                    )
                    # Keep the selection visible
                    self.tree.see(item)
            except Exception as e:
                print(f"Selection storage error: {e}")
    
    def on_selection_changed(self, event):
        selected = self.tree.selection()
        if selected:
            try:
                item = selected[0]
                values = self.tree.item(item)['values']
                if values and len(values) >= 2:
                    self.selected_process = {
                        'pid': int(values[0]),
                        'name': values[1],
                        'item_id': item
                    }
                    self.selected_label.config(
                        text=f"Selected: {values[1]} (PID: {values[0]})",
                        fg=self.accent
                    )
            except Exception as e:
                print(f"Selection change error: {e}")
        # Don't clear selected_process if selection is empty - keep last selection
    
    def on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.on_tree_select(event)
            self.show_details()
    
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
            
            try:
                values = self.tree.item(item)['values']
                if values and len(values) >= 2:
                    self.selected_process = {
                        'pid': int(values[0]),
                        'name': values[1],
                        'item_id': item
                    }
                    self.selected_label.config(
                        text=f"Selected: {values[1]} (PID: {values[0]})",
                        fg=self.accent
                    )
            except Exception as e:
                print(f"Context menu error: {e}")
            
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()
    
    def sort_by(self, col):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
        
        self.sort_column = col
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        
        try:
            items.sort(key=lambda x: float(str(x[0]).rstrip('%').split()[0]), reverse=self.sort_reverse)
        except:
            items.sort(reverse=self.sort_reverse)
        
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
    
    def end_task(self):
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
            name = self.selected_process['name']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process to end")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
            name = values[1]
        
        if messagebox.askyesno("Confirm", f"End process '{name}' (PID: {pid})?"):
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                
                self.add_alert(f"Process terminated: {name} (PID: {pid})")
                messagebox.showinfo("Success", f"Process {name} terminated successfully")
                self.selected_process = None
                self.selected_label.config(text="No process selected", fg=self.fg_dim)
                self.refresh_data()
            except psutil.NoSuchProcess:
                messagebox.showerror("Error", "Process no longer exists")
            except psutil.AccessDenied:
                messagebox.showerror("Error", "Access denied. Try running as administrator.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def show_details(self):
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
        
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                try:
                    exe_path = proc.exe()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    exe_path = "Access Denied"
                
                try:
                    cmdline = ' '.join(proc.cmdline())
                    if not cmdline:
                        cmdline = "N/A"
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    cmdline = "Access Denied"
                
                try:
                    username = proc.username()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    username = "Access Denied"
                
                try:
                    parent_pid = proc.ppid()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    parent_pid = "N/A"
                
                try:
                    cpu_percent = proc.cpu_percent(interval=0.1)
                except:
                    cpu_percent = 0
                
                try:
                    mem_percent = proc.memory_percent()
                except:
                    mem_percent = 0
                
                details = [
                    f"PID: {proc.pid}",
                    f"Name: {proc.name()}",
                    f"Status: {proc.status()}",
                    f"CPU: {cpu_percent:.1f}%",
                    f"Memory: {mem_percent:.2f}%",
                    f"Threads: {proc.num_threads()}",
                    f"Executable: {exe_path}",
                    f"Command Line: {cmdline}",
                    f"User: {username}",
                    f"Created: {datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Parent PID: {parent_pid}"
                ]
            
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Process Details - {proc.name()}")
            detail_window.geometry("600x400")
            detail_window.configure(bg=self.bg_dark)
            
            text_widget = tk.Text(detail_window, wrap=tk.WORD, font=('Consolas', 10),
                                 bg=self.bg_darker, fg=self.fg_light, insertbackground=self.fg_light,
                                 selectbackground=self.accent, relief=tk.FLAT, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget.insert(1.0, "\n".join(details))
            text_widget.config(state=tk.DISABLED)
            
            close_btn = tk.Button(detail_window, text="Close", command=detail_window.destroy,
                                 font=('Arial', 10, 'bold'), bg=self.accent, fg='white', 
                                 relief=tk.FLAT, width=15, cursor='hand2', activebackground=self.accent_hover)
            close_btn.pack(pady=10)
            
        except psutil.NoSuchProcess:
            messagebox.showerror("Error", "Process no longer exists")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def open_file_location(self):
        self.root.update_idletasks()
        
        if self.selected_process:
            pid = self.selected_process['pid']
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Select a process")
                return
            values = self.tree.item(selected[0])['values']
            pid = int(values[0])
        
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            folder = os.path.dirname(exe_path)
            
            if platform.system() == 'Windows':
                os.startfile(folder)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
                
        except psutil.AccessDenied:
            messagebox.showerror("Error", "Access denied")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def export_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                               filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["PID", "Name", "Status", "CPU%", "Memory%", "Memory(MB)", "Threads", "User", "Runtime"])
                
                for item in self.tree.get_children():
                    values = self.tree.item(item)['values']
                    writer.writerow(values)
            
            self.add_alert(f"Process data exported to {filename}")
            messagebox.showinfo("Success", f"Data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")


if __name__ == "__main__":
    try:
        print("Starting Enhanced Task Manager Pro...")
        root = tk.Tk()
        root.lift()
        root.attributes('-topmost', True)
        root.after(100, lambda: root.attributes('-topmost', False))
        print("Window created successfully")
        app = TaskManager(root)
        print("Enhanced Task Manager initialized with new features!")
        print("\nNEW FEATURES:")
        print("- 👁 Process Monitoring: Watch specific processes")
        print("- 🔒 Suspend/Resume: Pause and resume processes")
        print("- ⚡ Auto-Kill Rules: Automatically terminate resource-heavy processes")
        print("- 📸 Snapshots: Save system state for later comparison")
        print("- 🔔 Alert System: Track all system events")
        print("- ⚡ Priority Control: Change process priority levels")
        root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
    
    def clear_history(self):
        """Clear all snapshots"""
        if self.process_snapshots and messagebox.askyesno("Confirm", "Clear all snapshots?"):
            self.process_snapshots.clear()
            self.update_history_display()
            self.add_alert("Cleared all snapshots")
    
    def clear_alerts(self):
        """Clear all alerts"""
        if self.alert_log and messagebox.askyesno("Confirm", "Clear all alerts?"):
            self.alert_log.clear()
            self.update_alerts_display()
    
    def export_alerts(self):
        """Export alert log"""
        if not self.alert_log:
            messagebox.showinfo("Info", "No alerts to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("\n".join(self.alert_log))
                messagebox.showinfo("Success", f"Alerts exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")