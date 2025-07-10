#!/usr/bin/env python3
"""
MuchFun - Audio-Reactive Device Controller
Enhanced with frequency band control and circular audio visualizer
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
import pyaudio
import numpy as np
import time
import logging
import traceback
import os
import queue
from datetime import datetime
from buttplug import Client, WebsocketConnector, ProtocolSpec

# Matplotlib imports for visualizer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation

class MuchFunApp:
    def __init__(self, root):
        # Setup logging first
        self.setup_logging()
        self.logger = logging.getLogger('MuchFun')
        
        self.logger.info("Starting MuchFun application")
        
        self.root = root
        self.root.title("MuchFun - Audio Device Controller")
        self.root.geometry("1400x1000")  # Increased size for visualizer
        self.root.resizable(True, True)
        
        # Buttplug client setup
        self.client = None
        self.device = None
        self.connected = False
        
        # Audio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_enabled = False
        
        # Control variables
        self.intensity = tk.DoubleVar(value=0.0)
        self.sensitivity = tk.DoubleVar(value=50.0)
        self.update_rate = 5.0  # Fixed at 5 commands per second
        self.audio_intensity = 0.0
        self.manual_intensity = 0.0
        
        # NEW: Frequency band control with thread-safe caching
        self.frequency_focus = tk.DoubleVar(value=0.0)  # -1=bass, 0=mids, 1=treble
        self.bass_energy = 0.0
        self.mids_energy = 0.0
        self.treble_energy = 0.0
        self.current_frequency_mix = 0.0
        
        # Thread-safe cached values for background threads
        self._cached_frequency_focus = 0.0
        self._cached_sensitivity = 50.0
        self._cached_verbose_logging = False
        
        # Thread-safe UI update queue
        self.ui_update_queue = queue.Queue()
        
        # Pattern/Loop control variables
        self.pattern_enabled = False
        self.pattern_type = "wave"
        self.pattern_intensity = tk.DoubleVar(value=50.0)
        self.pattern_rate = tk.DoubleVar(value=50.0)
        self.pattern_randomness = tk.DoubleVar(value=0.0)
        self.pattern_current_intensity = 0.0
        self.pattern_thread = None
        self.pattern_time = 0.0
        
        # Audio smoothing settings
        self.smoothing_type = "adaptive"
        self.smoothing_strength = 0.3
        self.attack_time = 0.05
        self.decay_time = 0.1
        
        # Logging control
        self.verbose_logging = tk.BooleanVar(value=False)
        
        # Audio visualizer setup
        self.visualizer_enabled = tk.BooleanVar(value=True)
        self.visualizer_animation = None
        self.visualizer_data = np.zeros(64)  # 64 frequency bins for smooth circular display
        self.visualizer_smoothed = np.zeros(64)
        
        # UI variables (initialize before UI creation)
        self.smoothing_type_var = None
        self.smoothing_strength_var = None
        self.attack_time_var = None
        self.decay_time_var = None
        self.smoothing_desc_var = None
        self.smoothed_value_var = None
        
        # Threading
        self.loop = None
        self.loop_thread = None
        self.audio_thread = None
        self.running = True
        
        # Statistics tracking
        self.commands_sent = 0
        self.last_stats_time = time.time()
        
        self.setup_ui()
        self.start_async_loop()
        
    def setup_logging(self):
        """Setup logging to both file and console"""
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"muchfun_{timestamp}.log")
        
        # Configure logging - start with INFO level
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()  # Also log to console
            ]
        )
        
        # Log system info
        logger = logging.getLogger('MuchFun')
        logger.info(f"Log file created: {log_file}")
        logger.info(f"Python version: {os.sys.version}")
        logger.info(f"Platform: {os.name}")
        
    def toggle_verbose_logging(self):
        """Toggle between INFO and DEBUG logging levels"""
        if self.verbose_logging.get():
            # Enable DEBUG for both MuchFun and websocket_connector
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger('websocket_connector').setLevel(logging.DEBUG)
            logging.getLogger('MuchFun Controller').setLevel(logging.DEBUG)
            self.logger.info("Verbose logging enabled (DEBUG level)")
        else:
            # Keep INFO level for main app but disable debug for websockets
            logging.getLogger().setLevel(logging.INFO)
            logging.getLogger('websocket_connector').setLevel(logging.INFO)
            logging.getLogger('MuchFun Controller').setLevel(logging.INFO)
            self.logger.info("Verbose logging disabled (INFO level)")
        
        # Update cached value immediately
        self.cache_verbose_logging_value()
        
    def log_exception(self, context="", exc_info=None):
        """Log an exception with full traceback"""
        if exc_info is None:
            exc_info = True
        self.logger.error(f"Exception in {context}", exc_info=exc_info)
        # Also print to console for immediate visibility
        print(f"ERROR in {context}:")
        traceback.print_exc()
        
    def setup_ui(self):
        """Setup the user interface with new layout"""
        # Configure dark theme
        plt.style.use('dark_background')
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure main grid weights for 2-column layout
        main_frame.columnconfigure(0, weight=1)  # Left column
        main_frame.columnconfigure(1, weight=1)  # Right column
        main_frame.rowconfigure(1, weight=1)     # Main content row
        
        # Title spans both columns
        title_label = ttk.Label(main_frame, text="🎮 MuchFun Controller", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # LEFT COLUMN - Manual Controls and Status
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        
        # Connection section
        conn_frame = ttk.LabelFrame(left_frame, text="Connection", padding="10")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        conn_frame.columnconfigure(0, weight=1)
        
        # Connection status and button
        conn_top_frame = ttk.Frame(conn_frame)
        conn_top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        conn_top_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(conn_top_frame, text="❌ Disconnected", foreground="red")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.connect_btn = ttk.Button(conn_top_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=1, sticky=tk.E)
        
        self.device_label = ttk.Label(conn_frame, text="No device connected")
        self.device_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # Settings section
        settings_frame = ttk.LabelFrame(left_frame, text="Settings", padding="10")
        settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Verbose logging toggle
        verbose_check = ttk.Checkbutton(settings_frame, text="Verbose Logging (Debug Mode)",
                                       variable=self.verbose_logging,
                                       command=self.toggle_verbose_logging)
        verbose_check.grid(row=0, column=0, sticky=tk.W)
        
        # Statistics display
        self.stats_label = ttk.Label(settings_frame, text="Commands sent: 0 (0.0/sec)")
        self.stats_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # Pattern/Loop control section
        pattern_frame = ttk.LabelFrame(left_frame, text="Pattern Control", padding="10")
        pattern_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        pattern_frame.columnconfigure(1, weight=1)
        
        # Pattern enable/disable
        self.pattern_enabled_var = tk.BooleanVar()
        pattern_enable_check = ttk.Checkbutton(pattern_frame, text="🔄 Enable Pattern Control",
                                             variable=self.pattern_enabled_var,
                                             command=self.toggle_pattern)
        pattern_enable_check.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        # Pattern type selection
        ttk.Label(pattern_frame, text="Pattern:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.pattern_type_var = tk.StringVar(value=self.pattern_type)
        pattern_combo = ttk.Combobox(pattern_frame, textvariable=self.pattern_type_var,
                                   values=["wave", "pulse", "ramp", "steady", "chaos", "heartbeat"],
                                   state="readonly", width=15)
        pattern_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(10, 0))
        pattern_combo.bind('<<ComboboxSelected>>', self.on_pattern_type_changed)
        
        # Pattern controls (compact)
        for i, (label, var, var_label) in enumerate([
            ("Max Intensity:", self.pattern_intensity, "pattern_intensity_label"),
            ("Pattern Speed:", self.pattern_rate, "pattern_rate_label"),
            ("Randomness:", self.pattern_randomness, "randomness_label")
        ]):
            ttk.Label(pattern_frame, text=label).grid(row=i+2, column=0, sticky=tk.W, pady=(10, 0))
            
            control_frame = ttk.Frame(pattern_frame)
            control_frame.grid(row=i+2, column=1, sticky=(tk.W, tk.E), pady=(10, 0), padx=(10, 0))
            control_frame.columnconfigure(0, weight=1)
            
            scale = ttk.Scale(control_frame, from_=0 if i < 2 else 0, to=100 if i < 2 else 100, 
                            orient=tk.HORIZONTAL, variable=var, length=150)
            scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            label_widget = ttk.Label(control_frame, text="50%")
            label_widget.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
            setattr(self, var_label, label_widget)
        
        # Pattern level indicator
        ttk.Label(pattern_frame, text="Pattern Level:").grid(row=5, column=0, sticky=tk.W, pady=(10, 0))
        
        pattern_level_frame = ttk.Frame(pattern_frame)
        pattern_level_frame.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=(10, 0), padx=(10, 0))
        pattern_level_frame.columnconfigure(0, weight=1)
        
        self.pattern_level_var = tk.DoubleVar()
        self.pattern_level_bar = ttk.Progressbar(pattern_level_frame, variable=self.pattern_level_var,
                                               maximum=100, length=150)
        self.pattern_level_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Manual control section
        manual_frame = ttk.LabelFrame(left_frame, text="Manual Control", padding="10")
        manual_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.rowconfigure(1, weight=1)
        
        # Intensity control
        intensity_label = ttk.Label(manual_frame, text="Intensity Control", font=("Arial", 10, "bold"))
        intensity_label.grid(row=0, column=0, pady=(0, 10))
        
        intensity_control_frame = ttk.Frame(manual_frame)
        intensity_control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        intensity_control_frame.columnconfigure(0, weight=1)
        intensity_control_frame.rowconfigure(0, weight=1)
        
        # Horizontal intensity slider
        self.intensity_scale = ttk.Scale(intensity_control_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                       variable=self.intensity, length=250,
                                       command=self.manual_intensity_changed)
        self.intensity_scale.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Intensity percentage label
        self.intensity_label = ttk.Label(intensity_control_frame, text="0%", font=("Arial", 12, "bold"))
        self.intensity_label.grid(row=1, column=0)
        
        # Emergency stop button
        self.stop_btn = ttk.Button(manual_frame, text="🛑 EMERGENCY STOP", 
                                 command=self.emergency_stop, style="Accent.TButton")
        self.stop_btn.grid(row=2, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # RIGHT COLUMN - Audio Controls and Visualizer
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        
        # Audio input section (moved to right)
        audio_frame = ttk.LabelFrame(right_frame, text="Audio Input", padding="10")
        audio_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        audio_frame.columnconfigure(1, weight=1)
        
        # Audio enable/disable
        self.audio_enabled_var = tk.BooleanVar()
        audio_enable_check = ttk.Checkbutton(audio_frame, text="🎤 Enable Microphone Control",
                                           variable=self.audio_enabled_var,
                                           command=self.toggle_audio)
        audio_enable_check.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        # Sensitivity control
        ttk.Label(audio_frame, text="Sensitivity:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        sens_frame = ttk.Frame(audio_frame)
        sens_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(10, 0))
        sens_frame.columnconfigure(0, weight=1)
        
        sensitivity_scale = ttk.Scale(sens_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                                    variable=self.sensitivity, length=150)
        sensitivity_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.sensitivity_label = ttk.Label(sens_frame, text="50%")
        self.sensitivity_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # NEW: Frequency Band Control
        freq_band_frame = ttk.LabelFrame(audio_frame, text="Frequency Focus", padding="10")
        freq_band_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        freq_band_frame.columnconfigure(0, weight=1)
        
        # Frequency focus slider
        ttk.Label(freq_band_frame, text="Bass ← → Treble").grid(row=0, column=0)
        
        freq_focus_frame = ttk.Frame(freq_band_frame)
        freq_focus_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        freq_focus_frame.columnconfigure(0, weight=1)
        
        self.frequency_focus_scale = ttk.Scale(freq_focus_frame, from_=-1, to=1, orient=tk.HORIZONTAL,
                                             variable=self.frequency_focus, length=200)
        self.frequency_focus_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.frequency_focus_label = ttk.Label(freq_focus_frame, text="Mids")
        self.frequency_focus_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Frequency band indicators
        freq_indicators_frame = ttk.Frame(freq_band_frame)
        freq_indicators_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        freq_indicators_frame.columnconfigure(0, weight=1)
        freq_indicators_frame.columnconfigure(1, weight=1)
        freq_indicators_frame.columnconfigure(2, weight=1)
        
        # Bass indicator
        bass_frame = ttk.Frame(freq_indicators_frame)
        bass_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Label(bass_frame, text="Bass", font=("Arial", 8)).grid(row=0, column=0)
        self.bass_var = tk.DoubleVar()
        self.bass_bar = ttk.Progressbar(bass_frame, variable=self.bass_var, maximum=100, length=60)
        self.bass_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Mids indicator
        mids_frame = ttk.Frame(freq_indicators_frame)
        mids_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(mids_frame, text="Mids", font=("Arial", 8)).grid(row=0, column=0)
        self.mids_var = tk.DoubleVar()
        self.mids_bar = ttk.Progressbar(mids_frame, variable=self.mids_var, maximum=100, length=60)
        self.mids_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Treble indicator
        treble_frame = ttk.Frame(freq_indicators_frame)
        treble_frame.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(5, 0))
        ttk.Label(treble_frame, text="Treble", font=("Arial", 8)).grid(row=0, column=0)
        self.treble_var = tk.DoubleVar()
        self.treble_bar = ttk.Progressbar(treble_frame, variable=self.treble_var, maximum=100, length=60)
        self.treble_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Audio level indicator
        ttk.Label(audio_frame, text="Mixed Level:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        
        level_frame = ttk.Frame(audio_frame)
        level_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(10, 0))
        level_frame.columnconfigure(0, weight=1)
        
        self.audio_level_var = tk.DoubleVar()
        self.audio_level_bar = ttk.Progressbar(level_frame, variable=self.audio_level_var,
                                             maximum=100, length=150)
        self.audio_level_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Audio Smoothing section
        smoothing_frame = ttk.LabelFrame(right_frame, text="Audio Smoothing", padding="15")
        smoothing_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        smoothing_frame.columnconfigure(1, weight=1)
        smoothing_frame.columnconfigure(3, weight=1)
        
        # Smoothing controls (simplified for space)
        ttk.Label(smoothing_frame, text="Type:").grid(row=0, column=0, sticky=tk.W)
        self.smoothing_type_var = tk.StringVar(value=self.smoothing_type)
        smoothing_combo = ttk.Combobox(smoothing_frame, textvariable=self.smoothing_type_var,
                                     values=["none", "simple", "adaptive", "momentum"],
                                     state="readonly", width=12)
        smoothing_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        smoothing_combo.bind('<<ComboboxSelected>>', self.on_smoothing_type_changed)
        
        ttk.Label(smoothing_frame, text="Strength:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        strength_frame = ttk.Frame(smoothing_frame)
        strength_frame.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(10, 0))
        strength_frame.columnconfigure(0, weight=1)
        
        self.smoothing_strength_var = tk.DoubleVar(value=self.smoothing_strength * 100)
        smoothing_strength_scale = ttk.Scale(strength_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                           variable=self.smoothing_strength_var, length=100,
                                           command=self.on_smoothing_strength_changed)
        smoothing_strength_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.smoothing_strength_label = ttk.Label(strength_frame, text=f"{int(self.smoothing_strength * 100)}%")
        self.smoothing_strength_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Real-time smoothing indicator
        ttk.Label(smoothing_frame, text="Smoothed:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        smoothed_frame = ttk.Frame(smoothing_frame)
        smoothed_frame.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        smoothed_frame.columnconfigure(0, weight=1)
        
        self.smoothed_value_var = tk.DoubleVar(value=0.0)
        self.smoothed_bar = ttk.Progressbar(smoothed_frame, variable=self.smoothed_value_var,
                                          maximum=100, length=250)
        self.smoothed_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Audio Visualizer section
        visualizer_frame = ttk.LabelFrame(right_frame, text="Audio Visualizer", padding="10")
        visualizer_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        visualizer_frame.columnconfigure(0, weight=1)
        visualizer_frame.rowconfigure(1, weight=1)
        
        # Visualizer controls
        viz_controls = ttk.Frame(visualizer_frame)
        viz_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        viz_enable_check = ttk.Checkbutton(viz_controls, text="🎵 Enable Visualizer",
                                         variable=self.visualizer_enabled,
                                         command=self.toggle_visualizer)
        viz_enable_check.grid(row=0, column=0, sticky=tk.W)
        
        # Setup matplotlib visualizer
        self.setup_visualizer(visualizer_frame)
        
        # Status bar spans both columns
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_text = tk.StringVar(value="Ready")
        status_bar = ttk.Label(status_frame, textvariable=self.status_text, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Configure root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Bind events
        self.sensitivity.trace_add('write', self.update_sensitivity_label)
        self.intensity.trace_add('write', self.update_intensity_label)
        self.pattern_intensity.trace_add('write', self.update_pattern_intensity_label)
        self.pattern_rate.trace_add('write', self.update_pattern_rate_label)
        self.pattern_randomness.trace_add('write', self.update_randomness_label)
        self.frequency_focus.trace_add('write', self.update_frequency_focus_label)
        
        # Add thread-safe value caching
        self.sensitivity.trace_add('write', self.cache_sensitivity_value)
        self.frequency_focus.trace_add('write', self.cache_frequency_focus_value)
        self.verbose_logging.trace_add('write', self.cache_verbose_logging_value)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start statistics update timer
        self.update_statistics()
        
        # Start UI update queue processor
        self.process_ui_updates()
        
    def hsl_to_rgb(self, h, s, l):
        """Convert HSL to RGB color format"""
        h = h / 360.0
        s = s / 100.0
        l = l / 100.0
        
        if s == 0:
            r = g = b = l  # achromatic
        else:
            def hue_to_rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return (r, g, b)
    
    def setup_visualizer(self, parent_frame):
        """Setup the circular audio visualizer"""
        # Create matplotlib figure with dark theme - SMALLER SIZE
        self.fig, self.ax = plt.subplots(
            subplot_kw={'projection': 'polar'}, 
            figsize=(2, 2),  # Reduced from (4, 4) to (2, 2)
            facecolor='#2b2b2b'
        )
        self.fig.patch.set_facecolor('#2b2b2b')
        
        # Configure the polar plot for a beautiful circular visualizer
        self.ax.set_facecolor('#1a1a1a')
        self.ax.grid(False)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.spines['polar'].set_visible(False)
        
        # Create bars for frequency visualization
        self.num_bars = 64
        self.angles = np.linspace(0, 2 * np.pi, self.num_bars, endpoint=False)
        self.bars = self.ax.bar(
            self.angles, 
            np.zeros(self.num_bars), 
            width=2*np.pi/self.num_bars, 
            bottom=0.1,  # Small inner circle
            align='edge'
        )
        
        # Set initial colors - beautiful gradient using RGB
        for i, bar in enumerate(self.bars):
            hue = (i / self.num_bars) * 360
            r, g, b = self.hsl_to_rgb(hue, 70, 50)
            bar.set_color((r, g, b))
            bar.set_alpha(0.8)
        
        self.ax.set_ylim(0, 1.0)
        
        # Embed in tkinter with better layout
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Make the plot tighter to eliminate padding
        self.fig.tight_layout(pad=0.1)
        
    def toggle_visualizer(self):
        """Toggle the audio visualizer"""
        if self.visualizer_enabled.get():
            self.start_visualizer()
        else:
            self.stop_visualizer()
            
    def start_visualizer(self):
        """Start the visualizer animation"""
        # Stop any existing animation first
        if self.visualizer_animation is not None:
            self.visualizer_animation.event_source.stop()
            self.visualizer_animation = None
        
        # Create new animation
        self.visualizer_animation = animation.FuncAnimation(
            self.fig, 
            self.update_visualizer, 
            frames=None, 
            interval=50,  # 20 FPS for smooth animation
            blit=False,
            cache_frame_data=False,
            repeat=True
        )
        
        # Force the canvas to draw and start the animation
        self.canvas.draw()
        self.canvas.start_event_loop(0.001)  # Kick-start the event loop
        
        self.logger.info("Audio visualizer started")
            
    def stop_visualizer(self):
        """Stop the visualizer animation"""
        if self.visualizer_animation:
            self.visualizer_animation.event_source.stop()
            self.visualizer_animation = None
        
        # Clear the bars immediately
        for bar in self.bars:
            bar.set_height(0.1)  # Reset to minimum height
        
        # Force redraw
        self.canvas.draw()
        self.logger.info("Audio visualizer stopped")
        
    def update_visualizer(self, frame):
        """Update the visualizer with current audio data"""
        if not self.visualizer_enabled.get():
            return self.bars
            
        # Smooth the visualizer data for fluid animation
        smoothing_factor = 0.3
        self.visualizer_smoothed = (smoothing_factor * self.visualizer_smoothed + 
                                   (1 - smoothing_factor) * self.visualizer_data)
        
        # Update bar heights and colors
        for i, bar in enumerate(self.bars):
            height = max(0.1, self.visualizer_smoothed[i] * 0.8 + 0.1)  # Keep minimum height
            bar.set_height(height)
            
            # Dynamic color based on frequency and intensity using RGB
            hue = (i / self.num_bars) * 360
            lightness = 30 + height * 40  # Brighter when more intense
            saturation = 60 + height * 30  # More saturated when more intense
            r, g, b = self.hsl_to_rgb(hue, saturation, lightness)
            bar.set_color((r, g, b))
            bar.set_alpha(0.7 + height * 0.3)  # More opaque when more intense
        
        return self.bars
        
    def analyze_frequency_bands(self, audio_data, sample_rate=44100):
        """Analyze audio data and extract frequency bands with strict noise filtering"""
        # Perform FFT
        fft = np.fft.rfft(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1/sample_rate)
        magnitudes = np.abs(fft)
        
        # Much stricter noise filtering approach
        # 1. Calculate RMS of the original audio signal
        audio_rms = np.sqrt(np.mean(audio_data**2))
        
        # 2. Much higher RMS threshold to avoid picking up background noise/feedback
        rms_threshold = 0.005  # Increased from 0.001 - much stricter
        
        if audio_rms < rms_threshold:
            # Complete silence - return zeros immediately
            return 0.0, 0.0, 0.0, np.zeros(64)
        
        # 3. Stricter frequency-domain noise gate
        # Use a higher percentile and stricter signal threshold
        noise_floor = np.percentile(magnitudes, 60)  # Use 60th percentile (was 40th)
        signal_threshold = noise_floor * 3.0  # Signals must be 3x above noise floor (was 2x)
        
        # Apply stricter noise gate
        magnitudes = np.where(magnitudes > signal_threshold, magnitudes - noise_floor, 0)
        
        # 4. Check if we have any significant frequencies left after noise filtering
        if np.sum(magnitudes) < 1.0:  # Very little energy remains after filtering
            return 0.0, 0.0, 0.0, np.zeros(64)
        
        # Define frequency ranges
        bass_mask = (freqs >= 20) & (freqs <= 250)
        mids_mask = (freqs >= 250) & (freqs <= 4000)
        treble_mask = (freqs >= 4000) & (freqs <= 20000)
        
        # Calculate energy in each band
        bass_energy = np.sum(magnitudes[bass_mask]) if np.any(bass_mask) else 0
        mids_energy = np.sum(magnitudes[mids_mask]) if np.any(mids_mask) else 0
        treble_energy = np.sum(magnitudes[treble_mask]) if np.any(treble_mask) else 0
        
        # Much stricter total energy threshold
        total_energy = bass_energy + mids_energy + treble_energy
        total_threshold = 15.0  # Increased from 5.0 - much stricter
        
        if total_energy < total_threshold:
            return 0.0, 0.0, 0.0, np.zeros(64)
        
        # Normalize energies
        bass_energy /= total_energy
        mids_energy /= total_energy
        treble_energy /= total_energy
        
        # Create visualizer data with same strict filtering
        if len(magnitudes) > 64:
            bin_edges = np.logspace(0, np.log10(len(magnitudes)), 65).astype(int)
            visualizer_data = np.zeros(64)
            for i in range(64):
                start_bin = bin_edges[i]
                end_bin = min(bin_edges[i+1], len(magnitudes))
                if end_bin > start_bin:
                    visualizer_data[i] = np.mean(magnitudes[start_bin:end_bin])
        else:
            visualizer_data = np.pad(magnitudes, (0, max(0, 64 - len(magnitudes))))[:64]
        
        # Normalize and clean visualizer data with stricter threshold
        max_viz = np.max(visualizer_data)
        if max_viz > 0:
            visualizer_data = visualizer_data / max_viz
            # Much stricter threshold to remove noise in visualizer
            visualizer_data = np.where(visualizer_data < 0.15, 0, visualizer_data)  # Increased from 0.05
        
        return bass_energy, mids_energy, treble_energy, visualizer_data
        
    def process_ui_updates(self):
        """Process UI updates from the queue in the main thread"""
        try:
            # Process all queued UI updates
            while True:
                try:
                    update_func = self.ui_update_queue.get_nowait()
                    update_func()  # Execute the UI update
                except queue.Empty:
                    break
            
            # Schedule next processing
            self.root.after(20, self.process_ui_updates)  # Check every 20ms for smooth updates
        except Exception as e:
            self.log_exception("process_ui_updates", exc_info=True)
            
    def calculate_frequency_mix(self, bass, mids, treble, focus_value):
        """Calculate the mixed intensity based on frequency focus"""
        # focus_value: -1 = bass, 0 = mids, 1 = treble
        if focus_value <= 0:
            # Blend between bass and mids
            blend_factor = (focus_value + 1) / 2  # 0 to 1
            mixed_intensity = bass * (1 - blend_factor) + mids * blend_factor
        else:
            # Blend between mids and treble
            blend_factor = focus_value  # 0 to 1
            mixed_intensity = mids * (1 - blend_factor) + treble * blend_factor
        
        return mixed_intensity
        
    def update_statistics(self):
        """Update command statistics display"""
        try:
            current_time = time.time()
            time_diff = current_time - self.last_stats_time
            
            if time_diff >= 1.0:  # Update every second
                commands_per_sec = self.commands_sent / time_diff if time_diff > 0 else 0
                self.stats_label.config(text=f"Commands sent: {self.commands_sent} ({commands_per_sec:.1f}/sec)")
                self.commands_sent = 0
                self.last_stats_time = current_time
                
            # Schedule next update
            self.root.after(1000, self.update_statistics)
        except Exception as e:
            self.log_exception("update_statistics", exc_info=True)
        
    def apply_audio_smoothing(self, current_intensity, target_intensity, delta_time):
        """Apply different smoothing algorithms with faster decay for silence"""
        
        # Much lower threshold for cutting to zero (faster silence response)
        cutoff_threshold = 0.01  # Increased from 0.005 to cut off more aggressively
        
        if self.smoothing_type == "none":
            return target_intensity
            
        elif self.smoothing_type == "simple":
            # Simple exponential smoothing with faster decay to zero
            smooth_factor = self.smoothing_strength
            result = smooth_factor * current_intensity + (1 - smooth_factor) * target_intensity
            
            # Apply cutoff threshold more aggressively
            if result < cutoff_threshold:
                return 0.0
            return result
            
        elif self.smoothing_type == "adaptive":
            # Adaptive smoothing with much faster decay to silence
            if target_intensity > current_intensity:
                # Fast attack for increases
                attack_factor = min(1.0, delta_time / max(0.01, self.attack_time))
                result = current_intensity + (target_intensity - current_intensity) * attack_factor
            else:
                # Much more aggressive decay - especially when target is zero
                if target_intensity == 0.0:
                    # When target is zero, use very fast exponential decay
                    decay_rate = 3.0 / max(0.01, self.decay_time)  # 3x faster decay to zero
                    decay_factor = 1.0 - min(0.99, delta_time * decay_rate)  # Up to 99% decay per frame
                    result = current_intensity * decay_factor
                else:
                    # When target is not zero, use normal decay
                    decay_factor = min(1.0, delta_time / max(0.01, self.decay_time))
                    result = current_intensity + (target_intensity - current_intensity) * decay_factor
            
            # Apply cutoff threshold more aggressively
            if result < cutoff_threshold:
                return 0.0
            return max(0.0, min(1.0, result))
                
        elif self.smoothing_type == "momentum":
            # Momentum-based smoothing with faster settling to zero
            if not hasattr(self, '_audio_velocity'):
                self._audio_velocity = 0.0
                
            # Calculate desired change
            desired_change = target_intensity - current_intensity
            
            # More aggressive settings for faster decay to silence
            momentum_factor = 0.3   # Reduced from 0.5 for faster response
            damping_factor = 0.6    # Increased from 0.4 for more damping
            responsiveness = 2.0
            
            # Update velocity
            self._audio_velocity = (momentum_factor * self._audio_velocity + 
                                  (1 - momentum_factor) * desired_change * responsiveness)
            
            # Apply stronger damping, especially when target is zero
            damping_multiplier = 3.0 if target_intensity == 0.0 else 1.0
            self._audio_velocity *= (1 - damping_factor * damping_multiplier * delta_time)
            
            # Calculate new intensity
            new_intensity = current_intensity + self._audio_velocity * delta_time
            
            # Much more aggressive cutoff for momentum
            if new_intensity < cutoff_threshold or target_intensity == 0.0:
                self._audio_velocity = 0.0  # Reset velocity when cutting to zero
                return 0.0
                
            # Clamp to valid range
            return max(0.0, min(1.0, new_intensity))
            
        return target_intensity

    def start_async_loop(self):
        """Start the asyncio event loop in a separate thread"""
        try:
            self.logger.info("Starting async event loop")
            def run_loop():
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_forever()
            
            self.loop_thread = threading.Thread(target=run_loop, daemon=True)
            self.loop_thread.start()
            
            # Wait a moment for the loop to start
            time.sleep(0.1)
            self.logger.info("Async event loop started successfully")
        except Exception as e:
            self.log_exception("start_async_loop", exc_info=True)
        
    def run_async(self, coro):
        """Run an async function in the async loop"""
        try:
            if self.loop:
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                return future
        except Exception as e:
            self.log_exception("run_async", exc_info=True)
        
    def toggle_connection(self):
        """Toggle connection to Buttplug server"""
        try:
            self.logger.info(f"Toggle connection - currently connected: {self.connected}")
            if not self.connected:
                self.run_async(self.connect_to_server())
            else:
                self.run_async(self.disconnect_from_server())
        except Exception as e:
            self.log_exception("toggle_connection", exc_info=True)
            
    async def connect_to_server(self):
        """Connect to Buttplug server"""
        try:
            self.logger.info("Attempting to connect to Buttplug server")
            self.client = Client("MuchFun Controller", ProtocolSpec.v3)
            connector = WebsocketConnector("ws://localhost:12345")
            await self.client.connect(connector)
            
            devices = self.client.devices
            self.logger.info(f"Connected! Found {len(devices)} devices")
            
            if len(devices) > 0:
                self.device = list(devices.values())[0]
                self.logger.info(f"Using device: {self.device.name}")
                self.root.after(0, self.update_connection_status, True, 
                              f"Connected to {self.device.name}")
            else:
                self.logger.warning("Connected but no devices found")
                self.root.after(0, self.update_connection_status, True, 
                              "Connected - No devices found")
                
        except Exception as e:
            self.log_exception("connect_to_server", exc_info=True)
            self.root.after(0, self.update_connection_status, False, f"Connection failed: {e}")
            
    async def disconnect_from_server(self):
        """Disconnect from Buttplug server"""
        try:
            if self.client:
                await self.client.disconnect()
            self.root.after(0, self.update_connection_status, False, "Disconnected")
        except Exception as e:
            self.root.after(0, self.update_connection_status, False, f"Disconnect error: {e}")
            
    def update_connection_status(self, connected, message):
        """Update connection status in UI"""
        self.connected = connected
        if connected:
            self.status_label.config(text="✅ Connected", foreground="green")
            self.connect_btn.config(text="Disconnect")
            self.device_label.config(text=message)
        else:
            self.status_label.config(text="❌ Disconnected", foreground="red")
            self.connect_btn.config(text="Connect")
            self.device_label.config(text="No device connected")
            self.device = None
        self.status_text.set(message)
        
    def toggle_audio(self):
        """Enable/disable audio control"""
        self.audio_enabled = self.audio_enabled_var.get()
        if self.audio_enabled:
            self.start_audio()
        else:
            self.stop_audio()
            
    def start_audio(self):
        """Start audio input processing"""
        try:
            self.logger.info("Starting microphone input processing")
            
            if self.audio_thread and self.audio_thread.is_alive():
                self.logger.warning("Audio thread already running")
                return
                
            # Audio settings - microphone only
            chunk = 1024
            format = pyaudio.paFloat32
            channels = 1  # Mono microphone input
            rate = 44100
            
            self.logger.info(f"Audio config - Microphone, Channels: {channels}, Rate: {rate}")
            
            # Use default microphone
            self.stream = self.audio.open(
                format=format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )
            
            self.audio_thread = threading.Thread(target=self.audio_worker, daemon=True)
            self.audio_thread.start()
            
            self.logger.info("Microphone started successfully")
            self.status_text.set("Microphone audio started")
            
        except Exception as e:
            self.log_exception("start_audio", exc_info=True)
            messagebox.showerror("Audio Error", f"Failed to start microphone: {e}")
            self.audio_enabled_var.set(False)
            
    def stop_audio(self):
        """Stop audio input processing"""
        self.audio_enabled = False
        if self.stream:
            try:
                if not self.stream.is_stopped():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                self.logger.warning(f"Error stopping audio stream: {e}")
            finally:
                self.stream = None
        self.audio_intensity = 0.0
        self.bass_energy = 0.0
        self.mids_energy = 0.0
        self.treble_energy = 0.0
        self.visualizer_data = np.zeros(64)
        
        self.root.after(0, lambda: self.audio_level_var.set(0))
        self.root.after(0, lambda: self.smoothed_value_var.set(0))
        self.root.after(0, lambda: self.bass_var.set(0))
        self.root.after(0, lambda: self.mids_var.set(0))
        self.root.after(0, lambda: self.treble_var.set(0))
        self.status_text.set("Microphone stopped")
        
    def toggle_pattern(self):
        """Enable/disable pattern control"""
        self.pattern_enabled = self.pattern_enabled_var.get()
        if self.pattern_enabled:
            self.start_pattern()
        else:
            self.stop_pattern()
            
    def start_pattern(self):
        """Start pattern generation"""
        try:
            self.logger.info(f"Starting pattern control - Type: {self.pattern_type}")
            
            if self.pattern_thread and self.pattern_thread.is_alive():
                self.logger.warning("Pattern thread already running")
                return
                
            self.pattern_time = 0.0
            self.pattern_thread = threading.Thread(target=self.pattern_worker, daemon=True)
            self.pattern_thread.start()
            
            self.logger.info("Pattern control started successfully")
            self.status_text.set(f"Pattern control started: {self.pattern_type}")
            
        except Exception as e:
            self.log_exception("start_pattern", exc_info=True)
            self.pattern_enabled_var.set(False)
            
    def stop_pattern(self):
        """Stop pattern generation"""
        self.pattern_enabled = False
        self.pattern_current_intensity = 0.0
        self.root.after(0, lambda: self.pattern_level_var.set(0))
        self.status_text.set("Pattern control stopped")
        
    def generate_pattern_value(self, time_val, pattern_type, rate_factor):
        """Generate pattern value based on type and time"""
        import math
        import random
        
        # Adjust time based on rate (higher rate = faster patterns)
        adjusted_time = time_val * rate_factor
        
        if pattern_type == "wave":
            # Smooth sine wave
            return (math.sin(adjusted_time) + 1) / 2
            
        elif pattern_type == "pulse":
            # Square wave with smooth transitions
            cycle = adjusted_time % (2 * math.pi)
            if cycle < math.pi:
                return 1.0
            else:
                return 0.0
                
        elif pattern_type == "ramp":
            # Sawtooth wave
            cycle = adjusted_time % (2 * math.pi)
            return cycle / (2 * math.pi)
            
        elif pattern_type == "steady":
            # Steady value with small variations
            return 0.7 + 0.1 * math.sin(adjusted_time * 0.5)
            
        elif pattern_type == "chaos":
            # Chaotic but smooth changes
            return (math.sin(adjusted_time) * math.cos(adjusted_time * 1.618) + 1) / 2
            
        elif pattern_type == "heartbeat":
            # Double pulse like heartbeat
            cycle = adjusted_time % (2 * math.pi)
            if cycle < 0.3:
                return math.sin(cycle * 10) ** 2
            elif cycle < 0.8:
                return math.sin((cycle - 0.3) * 12) ** 2
            else:
                return 0.0
                
        return 0.5  # Default fallback
    
    def pattern_worker(self):
        """Pattern generation worker thread"""
        self.logger.info("Pattern worker thread started")
        
        last_send_time = 0
        start_time = time.time()
        
        while self.pattern_enabled and self.running:
            try:
                current_time = time.time()
                self.pattern_time = current_time - start_time
                
                # Get current pattern settings
                max_intensity = float(self.pattern_intensity.get()) / 100.0
                rate_factor = float(self.pattern_rate.get()) / 100.0
                randomness = float(self.pattern_randomness.get()) / 100.0
                
                # Generate base pattern value (0.0 to 1.0)
                base_value = self.generate_pattern_value(self.pattern_time, self.pattern_type, rate_factor)
                
                # Apply randomness if enabled
                if randomness > 0:
                    import random
                    random_offset = (random.random() - 0.5) * 2 * randomness * 0.3  # Scale randomness
                    base_value = max(0.0, min(1.0, base_value + random_offset))
                
                # Scale by max intensity
                self.pattern_current_intensity = base_value * max_intensity
                
                if self._cached_verbose_logging:
                    self.logger.debug(f"Pattern - Type: {self.pattern_type}, Base: {base_value:.3f}, "
                                    f"Final: {self.pattern_current_intensity:.3f}")
                
                # Update UI
                pattern_percentage = self.pattern_current_intensity * 100
                try:
                    self.ui_update_queue.put(lambda: self.pattern_level_var.set(pattern_percentage))
                except queue.Full:
                    pass  # Skip update if queue is full
                
                # Send to device with rate limiting
                send_interval = 1.0 / self.update_rate
                should_send = (self.device and self.pattern_enabled and 
                             current_time - last_send_time >= send_interval)
                
                if should_send:
                    if self.verbose_logging.get():
                        self.logger.debug(f"Sending pattern to device - Intensity: {self.pattern_current_intensity:.4f}")
                    
                    # Queue device update instead of calling tkinter directly
                    try:
                        self.ui_update_queue.put(self.update_device_from_pattern)
                    except queue.Full:
                        pass  # Skip update if queue is full
                    last_send_time = current_time
                    
            except Exception as e:
                if self.pattern_enabled:
                    self.log_exception("pattern_worker", exc_info=True)
                break
                
            time.sleep(0.05)  # 20Hz update rate for smooth patterns
            
        self.logger.info("Pattern worker thread ended")
        
    def update_device_from_pattern(self):
        """Update device intensity from pattern"""
        try:
            if self.device and self.connected:
                # Combine pattern, audio, and manual intensity (max of all)
                manual_val = float(self.intensity.get()) / 100.0
                combined_intensity = max(self.pattern_current_intensity, self.audio_intensity, manual_val)
                
                if self.verbose_logging.get():
                    self.logger.debug(f"Device update - Pattern: {self.pattern_current_intensity:.3f}, "
                                    f"Audio: {self.audio_intensity:.3f}, Manual: {manual_val:.3f}, "
                                    f"Combined: {combined_intensity:.3f}")
                
                self.run_async(self.send_intensity(combined_intensity))
        except Exception as e:
            self.log_exception("update_device_from_pattern", exc_info=True)
        
    def audio_worker(self):
        """Audio processing worker thread with frequency analysis"""
        self.logger.info("Audio worker thread started")
        
        # Audio smoothing variables
        smoothed_intensity = 0.0
        last_send_time = 0
        last_process_time = time.time()
        
        # Noise floor - ignore anything below this threshold
        noise_floor = 0.02  # Ignore audio below 2% to filter background noise
        
        # Reduced logging frequency
        log_counter = 0
        
        while self.audio_enabled and self.stream and self.running:
            try:
                current_time = time.time()
                delta_time = current_time - last_process_time
                last_process_time = current_time
                
                if self.stream.is_stopped():
                    self.logger.warning("Audio stream is stopped, breaking from worker loop")
                    break
                    
                data = self.stream.read(1024, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.float32)
                
                # NEW: Analyze frequency bands
                bass, mids, treble, viz_data = self.analyze_frequency_bands(audio_data, 44100)
                
                # Store frequency data
                self.bass_energy = bass
                self.mids_energy = mids
                self.treble_energy = treble
                self.visualizer_data = viz_data
                
                # Calculate mixed intensity based on frequency focus
                focus_value = self._cached_frequency_focus  # Use cached value instead of direct tkinter access
                frequency_mix = self.calculate_frequency_mix(bass, mids, treble, focus_value)
                
                # Apply sensitivity
                sensitivity_factor = self._cached_sensitivity / 100.0  # Use cached value
                target_intensity = frequency_mix * sensitivity_factor
                
                # Apply noise floor
                if target_intensity < noise_floor:
                    target_intensity = 0.0
                
                # Apply smoothing
                smoothed_intensity = self.apply_audio_smoothing(
                    smoothed_intensity, target_intensity, delta_time
                )
                
                # Cap the intensity at a reasonable maximum
                self.audio_intensity = float(min(0.8, smoothed_intensity))  # Cap at 80% max
                
                # More frequent logging for debugging and better UI updates
                log_counter += 1
                if self._cached_verbose_logging and log_counter % 50 == 0:  # Use cached value instead
                    self.logger.debug(f"Audio - Bass: {bass:.3f}, Mids: {mids:.3f}, Treble: {treble:.3f}, "
                                    f"Focus: {focus_value:.2f}, Mixed: {frequency_mix:.3f}, "
                                    f"Sensitivity: {sensitivity_factor:.2f}, Final: {self.audio_intensity:.3f}")
                    # Also log what we're setting the UI bars to
                    self.logger.debug(f"UI Update - Bass bar: {bass*100:.1f}%, Mids bar: {mids*100:.1f}%, "
                                    f"Treble bar: {treble*100:.1f}%, Mixed bar: {frequency_mix*100:.1f}%")
                
                # Update UI frequency indicators using queue for thread safety
                bass_pct = bass * 100
                mids_pct = mids * 100  
                treble_pct = treble * 100
                mix_pct = frequency_mix * 100
                smoothed_pct = self.audio_intensity * 100
                
                # Queue UI updates instead of calling tkinter directly
                try:
                    self.ui_update_queue.put(lambda: self.bass_var.set(bass_pct))
                    self.ui_update_queue.put(lambda: self.mids_var.set(mids_pct))
                    self.ui_update_queue.put(lambda: self.treble_var.set(treble_pct))
                    self.ui_update_queue.put(lambda: self.audio_level_var.set(mix_pct))
                    self.ui_update_queue.put(lambda: self.smoothed_value_var.set(smoothed_pct))
                except queue.Full:
                    pass  # Skip updates if queue is full
                
                # Send to device with configurable rate limiting (5 commands/sec)
                send_interval = 1.0 / self.update_rate  # 0.2 seconds for 5 commands/sec
                should_send = (self.device and self.audio_enabled and 
                             current_time - last_send_time >= send_interval)
                
                if should_send and (self.audio_intensity > 0.0 or 
                   (hasattr(self, '_last_sent_intensity') and self._last_sent_intensity > 0.0)):
                    
                    if self._cached_verbose_logging:  # Use cached value instead
                        self.logger.debug(f"Sending to device - Intensity: {self.audio_intensity:.4f}")
                    
                    # Queue device update instead of calling tkinter directly
                    try:
                        self.ui_update_queue.put(self.update_device_from_audio)
                    except queue.Full:
                        pass  # Skip update if queue is full
                    last_send_time = current_time
                    self._last_sent_intensity = self.audio_intensity
                    
            except Exception as e:
                if self.audio_enabled:  # Only show error if we're supposed to be running
                    self.log_exception("audio_worker", exc_info=True)
                break
                
            time.sleep(0.02)  # 50ms processing interval
            
        self.logger.info("Audio worker thread ended")
            
    def update_device_from_audio(self):
        """Update device intensity from audio input"""
        try:
            if self.device and self.connected:
                # Combine audio and manual intensity (max of both)
                manual_val = float(self.intensity.get()) / 100.0
                combined_intensity = max(self.audio_intensity, manual_val)
                
                if self.verbose_logging.get():
                    self.logger.debug(f"Device update - Audio: {self.audio_intensity:.3f}, Manual: {manual_val:.3f}, Combined: {combined_intensity:.3f}")
                
                self.run_async(self.send_intensity(combined_intensity))
        except Exception as e:
            self.log_exception("update_device_from_audio", exc_info=True)
            
    def manual_intensity_changed(self, value):
        """Handle manual intensity slider change"""
        try:
            self.manual_intensity = float(value) / 100.0
            
            if self.verbose_logging.get():
                self.logger.debug(f"Manual intensity changed to: {self.manual_intensity:.3f}")
            
            if self.device and self.connected and not self.audio_enabled and not self.pattern_enabled:
                # Only send manual control if audio and pattern are not enabled
                self.run_async(self.send_intensity(self.manual_intensity))
        except Exception as e:
            self.log_exception("manual_intensity_changed", exc_info=True)
            
    async def send_intensity(self, intensity):
        """Send intensity to device"""
        try:
            if self.device and len(self.device.actuators) > 0:
                # Convert to regular Python float to avoid JSON serialization issues
                intensity_float = float(intensity)
                
                if self.verbose_logging.get():
                    self.logger.debug(f"Sending intensity {intensity_float:.3f} to device")
                
                await self.device.actuators[0].command(intensity_float)
                self.commands_sent += 1
                
        except Exception as e:
            self.log_exception("send_intensity", exc_info=True)
            error_msg = f"Device error: {e}"
            self.root.after(0, lambda msg=error_msg: self.status_text.set(msg))
            
    def emergency_stop(self):
        """Emergency stop - immediately stop device"""
        try:
            self.logger.warning("EMERGENCY STOP ACTIVATED")
            
            if self.device:
                self.run_async(self.device.stop())
            self.intensity.set(0)
            self.manual_intensity = 0.0
            self.audio_enabled_var.set(False)
            self.pattern_enabled_var.set(False)
            
            # Reset smoothing state
            if hasattr(self, '_audio_velocity'):
                self._audio_velocity = 0.0
            
            # Safely stop all control methods
            try:
                self.stop_audio()
                self.stop_pattern()
            except Exception as e:
                self.log_exception("emergency_stop cleanup", exc_info=True)
                
            self.status_text.set("EMERGENCY STOP ACTIVATED")
            self.logger.info("Emergency stop completed")
        except Exception as e:
            self.log_exception("emergency_stop", exc_info=True)
        
    def update_sensitivity_label(self, *args):
        """Update sensitivity label"""
        self.sensitivity_label.config(text=f"{int(self.sensitivity.get())}%")
        
    def update_intensity_label(self, *args):
        """Update intensity label"""
        self.intensity_label.config(text=f"{int(self.intensity.get())}%")
        
    def update_pattern_intensity_label(self, *args):
        """Update pattern intensity label"""
        self.pattern_intensity_label.config(text=f"{int(self.pattern_intensity.get())}%")
        
    def update_pattern_rate_label(self, *args):
        """Update pattern rate label"""
        self.pattern_rate_label.config(text=f"{int(self.pattern_rate.get())}%")
        
    def update_randomness_label(self, *args):
        """Update randomness label"""
        self.randomness_label.config(text=f"{int(self.pattern_randomness.get())}%")
        
    def update_frequency_focus_label(self, *args):
        """Update frequency focus label"""
        try:
            focus_value = self.frequency_focus.get()
            if focus_value < -0.3:
                label = "Bass"
            elif focus_value > 0.3:
                label = "Treble"
            else:
                label = "Mids"
            self.frequency_focus_label.config(text=label)
        except:
            pass  # Ignore errors during shutdown
        
    def cache_sensitivity_value(self, *args):
        """Cache sensitivity value for thread-safe access"""
        try:
            self._cached_sensitivity = self.sensitivity.get()
        except:
            pass  # Ignore errors during shutdown
            
    def cache_frequency_focus_value(self, *args):
        """Cache frequency focus value for thread-safe access"""
        try:
            self._cached_frequency_focus = self.frequency_focus.get()
        except:
            pass  # Ignore errors during shutdown
            
    def cache_verbose_logging_value(self, *args):
        """Cache verbose logging value for thread-safe access"""
        try:
            self._cached_verbose_logging = self.verbose_logging.get()
        except:
            pass  # Ignore errors during shutdown
        """Update frequency focus label"""
        focus_value = self.frequency_focus.get()
        if focus_value < -0.3:
            label = "Bass"
        elif focus_value > 0.3:
            label = "Treble"
        else:
            label = "Mids"
        self.frequency_focus_label.config(text=label)
        
    def on_pattern_type_changed(self, event=None):
        """Handle pattern type selection change"""
        self.pattern_type = self.pattern_type_var.get()
        self.logger.info(f"Pattern type changed to: {self.pattern_type}")
        # Reset pattern time when changing type for immediate effect
        self.pattern_time = 0.0
        
    def on_smoothing_type_changed(self, event=None):
        """Handle smoothing type selection change"""
        self.smoothing_type = self.smoothing_type_var.get()
        self.logger.info(f"Smoothing type changed to: {self.smoothing_type}")
        
    def on_smoothing_strength_changed(self, value):
        """Handle smoothing strength slider change"""
        self.smoothing_strength = float(value) / 100.0
        self.smoothing_strength_label.config(text=f"{int(float(value))}%")
        if self.verbose_logging.get():
            self.logger.debug(f"Smoothing strength changed to: {self.smoothing_strength:.2f}")
        
    def on_closing(self):
        """Handle application closing"""
        self.running = False
        
        # Stop visualizer
        self.stop_visualizer()
        
        # Stop all control methods
        self.stop_audio()
        self.stop_pattern()
        
        # Disconnect from server
        if self.connected:
            self.run_async(self.disconnect_from_server())
            
        # Clean up audio
        if self.audio:
            self.audio.terminate()
            
        # Stop async loop
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
        self.root.destroy()

def main():
    """Main function"""
    # Check if required packages are available
    try:
        import pyaudio
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError as e:
        print("Missing required packages. Please install:")
        print("pip install pyaudio numpy matplotlib")
        print(f"Error: {e}")
        return
        
    root = tk.Tk()
    app = MuchFunApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()