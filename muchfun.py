#!/usr/bin/env python3
"""
MuchFun - Audio-Reactive Device Controller
A GUI application to control your device with audio input and manual controls
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
from datetime import datetime
from buttplug import Client, WebsocketConnector, ProtocolSpec

class MuchFunApp:
    def __init__(self, root):
        # Setup logging first
        self.setup_logging()
        self.logger = logging.getLogger('MuchFun')
        
        self.logger.info("Starting MuchFun application")
        
        self.root = root
        self.root.title("MuchFun - Audio Device Controller")
        self.root.geometry("1200x900")  # Changed to wider layout
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
        self.update_rate = 5.0  # Fixed at 5 commands per second (configurable in code)
        self.audio_intensity = 0.0
        self.manual_intensity = 0.0
        
        # Pattern/Loop control variables
        self.pattern_enabled = False
        self.pattern_type = "wave"
        self.pattern_intensity = tk.DoubleVar(value=50.0)  # Max intensity for patterns
        self.pattern_rate = tk.DoubleVar(value=50.0)       # Speed of pattern changes
        self.pattern_randomness = tk.DoubleVar(value=0.0)  # Amount of randomness
        self.pattern_current_intensity = 0.0
        self.pattern_thread = None
        self.pattern_time = 0.0
        
        # Audio smoothing settings (configurable)
        self.smoothing_type = "adaptive"  # "none", "simple", "adaptive", "momentum"
        self.smoothing_strength = 0.3  # 0.0 = no smoothing, 1.0 = maximum smoothing
        self.attack_time = 0.05  # How quickly to respond to increases (seconds)
        self.decay_time = 0.1   # How slowly to decay when audio stops (seconds)
        
        # Logging control
        self.verbose_logging = tk.BooleanVar(value=False)
        
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
            logging.getLogger().setLevel(logging.DEBUG)
            self.logger.info("Verbose logging enabled (DEBUG level)")
        else:
            logging.getLogger().setLevel(logging.INFO)
            self.logger.info("Verbose logging disabled (INFO level)")
        
    def log_exception(self, context="", exc_info=None):
        """Log an exception with full traceback"""
        if exc_info is None:
            exc_info = True
        self.logger.error(f"Exception in {context}", exc_info=exc_info)
        # Also print to console for immediate visibility
        print(f"ERROR in {context}:")
        traceback.print_exc()
        
    def setup_ui(self):
        """Setup the user interface with wider layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure main grid weights for 2-column layout
        main_frame.columnconfigure(0, weight=2)  # Left column (40%)
        main_frame.columnconfigure(1, weight=3)  # Right column (60%)
        main_frame.rowconfigure(1, weight=1)     # Main content row
        
        # Title spans both columns
        title_label = ttk.Label(main_frame, text="🎮 MuchFun Controller", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # LEFT COLUMN - Controls and Status
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        
        # Connection section
        conn_frame = ttk.LabelFrame(left_frame, text="Connection", padding="10")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        conn_frame.columnconfigure(0, weight=1)
        
        # Connection status and button in same row
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
        
        # Audio input section
        audio_frame = ttk.LabelFrame(left_frame, text="Audio Input", padding="10")
        audio_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        audio_frame.columnconfigure(1, weight=1)
        
        # Audio enable/disable
        self.audio_enabled_var = tk.BooleanVar()
        audio_enable_check = ttk.Checkbutton(audio_frame, text="🎤 Enable Microphone Control",
                                           variable=self.audio_enabled_var,
                                           command=self.toggle_audio)
        audio_enable_check.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        # Sensitivity control in compact layout
        ttk.Label(audio_frame, text="Sensitivity:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        sens_frame = ttk.Frame(audio_frame)
        sens_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(10, 0))
        sens_frame.columnconfigure(0, weight=1)
        
        sensitivity_scale = ttk.Scale(sens_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                                    variable=self.sensitivity, length=150)
        sensitivity_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.sensitivity_label = ttk.Label(sens_frame, text="50%")
        self.sensitivity_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Audio level indicator
        ttk.Label(audio_frame, text="Audio Level:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        
        level_frame = ttk.Frame(audio_frame)
        level_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(10, 0))
        level_frame.columnconfigure(0, weight=1)
        
        self.audio_level_var = tk.DoubleVar()
        self.audio_level_bar = ttk.Progressbar(level_frame, variable=self.audio_level_var,
                                             maximum=100, length=150)
        self.audio_level_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Pattern/Loop control section
        pattern_frame = ttk.LabelFrame(left_frame, text="Pattern Control", padding="10")
        pattern_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
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
        
        # Pattern intensity control
        ttk.Label(pattern_frame, text="Max Intensity:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        
        pattern_int_frame = ttk.Frame(pattern_frame)
        pattern_int_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(10, 0), padx=(10, 0))
        pattern_int_frame.columnconfigure(0, weight=1)
        
        pattern_intensity_scale = ttk.Scale(pattern_int_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                          variable=self.pattern_intensity, length=150)
        pattern_intensity_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.pattern_intensity_label = ttk.Label(pattern_int_frame, text="50%")
        self.pattern_intensity_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Pattern rate control
        ttk.Label(pattern_frame, text="Pattern Speed:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        
        pattern_rate_frame = ttk.Frame(pattern_frame)
        pattern_rate_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(10, 0), padx=(10, 0))
        pattern_rate_frame.columnconfigure(0, weight=1)
        
        pattern_rate_scale = ttk.Scale(pattern_rate_frame, from_=10, to=200, orient=tk.HORIZONTAL,
                                     variable=self.pattern_rate, length=150)
        pattern_rate_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.pattern_rate_label = ttk.Label(pattern_rate_frame, text="50%")
        self.pattern_rate_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Randomness control
        ttk.Label(pattern_frame, text="Randomness:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        
        randomness_frame = ttk.Frame(pattern_frame)
        randomness_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=(10, 0), padx=(10, 0))
        randomness_frame.columnconfigure(0, weight=1)
        
        randomness_scale = ttk.Scale(randomness_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                   variable=self.pattern_randomness, length=150)
        randomness_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.randomness_label = ttk.Label(randomness_frame, text="0%")
        self.randomness_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
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
        manual_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.rowconfigure(1, weight=1)
        
        # Intensity control in horizontal layout
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
        
        # RIGHT COLUMN - Audio Smoothing
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        
        # Audio Smoothing section (expanded in right column)
        smoothing_frame = ttk.LabelFrame(right_frame, text="Audio Smoothing", padding="15")
        smoothing_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        smoothing_frame.columnconfigure(1, weight=1)
        smoothing_frame.columnconfigure(3, weight=1)
        
        # Top row - Smoothing type and description
        ttk.Label(smoothing_frame, text="Smoothing Type:").grid(row=0, column=0, sticky=tk.W)
        self.smoothing_type_var = tk.StringVar(value=self.smoothing_type)
        smoothing_combo = ttk.Combobox(smoothing_frame, textvariable=self.smoothing_type_var,
                                     values=["none", "simple", "adaptive", "momentum"],
                                     state="readonly", width=15)
        smoothing_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        smoothing_combo.bind('<<ComboboxSelected>>', self.on_smoothing_type_changed)
        
        self.smoothing_desc_var = tk.StringVar()
        smoothing_desc = ttk.Label(smoothing_frame, textvariable=self.smoothing_desc_var, 
                                 foreground="gray", font=("Arial", 9))
        smoothing_desc.grid(row=0, column=2, columnspan=2, sticky=tk.W, padx=(20, 0))
        self.update_smoothing_description()
        
        # Second row - Smoothing strength and real-time indicator
        ttk.Label(smoothing_frame, text="Smoothing Strength:").grid(row=1, column=0, sticky=tk.W, pady=(15, 0))
        
        strength_frame = ttk.Frame(smoothing_frame)
        strength_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(15, 0), padx=(10, 0))
        strength_frame.columnconfigure(0, weight=1)
        
        self.smoothing_strength_var = tk.DoubleVar(value=self.smoothing_strength * 100)
        smoothing_strength_scale = ttk.Scale(strength_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                           variable=self.smoothing_strength_var, length=150,
                                           command=self.on_smoothing_strength_changed)
        smoothing_strength_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.smoothing_strength_label = ttk.Label(strength_frame, text=f"{int(self.smoothing_strength * 100)}%")
        self.smoothing_strength_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Real-time smoothing indicator
        ttk.Label(smoothing_frame, text="Smoothed Value:").grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=(15, 0))
        
        smoothed_frame = ttk.Frame(smoothing_frame)
        smoothed_frame.grid(row=1, column=3, sticky=(tk.W, tk.E), pady=(15, 0))
        smoothed_frame.columnconfigure(0, weight=1)
        
        self.smoothed_value_var = tk.DoubleVar(value=0.0)
        self.smoothed_bar = ttk.Progressbar(smoothed_frame, variable=self.smoothed_value_var,
                                          maximum=100, length=120)
        self.smoothed_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Third row - Attack and Decay times
        ttk.Label(smoothing_frame, text="Attack Time (sec):").grid(row=2, column=0, sticky=tk.W, pady=(15, 0))
        
        attack_frame = ttk.Frame(smoothing_frame)
        attack_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(15, 0), padx=(10, 0))
        attack_frame.columnconfigure(0, weight=1)
        
        self.attack_time_var = tk.DoubleVar(value=self.attack_time * 100)
        attack_time_scale = ttk.Scale(attack_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                                    variable=self.attack_time_var, length=150,
                                    command=self.on_attack_time_changed)
        attack_time_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.attack_time_label = ttk.Label(attack_frame, text=f"{self.attack_time:.3f}s")
        self.attack_time_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(smoothing_frame, text="Decay Time (sec):").grid(row=2, column=2, sticky=tk.W, padx=(20, 0), pady=(15, 0))
        
        decay_frame = ttk.Frame(smoothing_frame)
        decay_frame.grid(row=2, column=3, sticky=(tk.W, tk.E), pady=(15, 0))
        decay_frame.columnconfigure(0, weight=1)
        
        self.decay_time_var = tk.DoubleVar(value=self.decay_time * 100)
        decay_time_scale = ttk.Scale(decay_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                                   variable=self.decay_time_var, length=120,
                                   command=self.on_decay_time_changed)
        decay_time_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.decay_time_label = ttk.Label(decay_frame, text=f"{self.decay_time:.3f}s")
        self.decay_time_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Presets section
        preset_frame = ttk.LabelFrame(smoothing_frame, text="Quick Presets", padding="10")
        preset_frame.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(20, 0))
        preset_frame.columnconfigure(1, weight=1)
        preset_frame.columnconfigure(2, weight=1)
        preset_frame.columnconfigure(3, weight=1)
        
        ttk.Label(preset_frame, text="Presets:").grid(row=0, column=0, sticky=tk.W)
        
        ttk.Button(preset_frame, text="Responsive", width=12,
                  command=lambda: self.apply_preset("responsive")).grid(row=0, column=1, padx=(10, 5))
        ttk.Button(preset_frame, text="Smooth", width=12,
                  command=lambda: self.apply_preset("smooth")).grid(row=0, column=2, padx=5)
        ttk.Button(preset_frame, text="Bouncy", width=12,
                  command=lambda: self.apply_preset("bouncy")).grid(row=0, column=3, padx=5)
                  
        # Preset descriptions
        preset_desc = ttk.Label(preset_frame, 
                               text="Responsive: Quick response | Smooth: Gentle changes | Bouncy: Physics-based",
                               foreground="gray", font=("Arial", 8))
        preset_desc.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
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
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start statistics update timer
        self.update_statistics()
        
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
        """Apply different smoothing algorithms to audio intensity"""
        
        # Threshold for cutting to zero (prevents infinite decay)
        cutoff_threshold = 0.005  # Cut to zero below 0.5%
        
        if self.smoothing_type == "none":
            return target_intensity
            
        elif self.smoothing_type == "simple":
            # Simple exponential smoothing with improved decay
            smooth_factor = self.smoothing_strength
            result = smooth_factor * current_intensity + (1 - smooth_factor) * target_intensity
            
            # Apply cutoff threshold
            if result < cutoff_threshold and target_intensity == 0.0:
                return 0.0
            return result
            
        elif self.smoothing_type == "adaptive":
            # Improved adaptive smoothing - much more responsive decay
            if target_intensity > current_intensity:
                # Fast attack for increases
                attack_factor = min(1.0, delta_time / max(0.01, self.attack_time))
                result = current_intensity + (target_intensity - current_intensity) * attack_factor
            else:
                # More aggressive decay - exponential falloff
                if target_intensity == 0.0:
                    # When target is zero, use exponential decay for faster response
                    decay_rate = 1.0 / max(0.01, self.decay_time)  # Higher rate = faster decay
                    decay_factor = 1.0 - min(0.95, delta_time * decay_rate)  # Cap at 95% decay per frame
                    result = current_intensity * decay_factor
                else:
                    # When target is not zero, use linear interpolation
                    decay_factor = min(1.0, delta_time / max(0.01, self.decay_time))
                    result = current_intensity + (target_intensity - current_intensity) * decay_factor
            
            # Apply cutoff threshold
            if result < cutoff_threshold and target_intensity == 0.0:
                return 0.0
            return max(0.0, min(1.0, result))
                
        elif self.smoothing_type == "momentum":
            # Improved momentum-based smoothing with more stability
            if not hasattr(self, '_audio_velocity'):
                self._audio_velocity = 0.0
                
            # Calculate desired change
            desired_change = target_intensity - current_intensity
            
            # More conservative momentum settings for stability
            momentum_factor = 0.5   # Reduced from 0.7 for more stability
            damping_factor = 0.4    # Increased from 0.3 for more smoothing
            responsiveness = 2.0    # How quickly to respond to changes
            
            # Update velocity with momentum and responsiveness
            self._audio_velocity = (momentum_factor * self._audio_velocity + 
                                  (1 - momentum_factor) * desired_change * responsiveness)
            
            # Apply stronger damping to prevent oscillation
            self._audio_velocity *= (1 - damping_factor * delta_time)
            
            # Calculate new intensity
            new_intensity = current_intensity + self._audio_velocity * delta_time
            
            # Additional damping when approaching target
            distance_to_target = abs(target_intensity - current_intensity)
            if distance_to_target < 0.1:  # Close to target
                extra_damping = 0.8
                self._audio_velocity *= (1 - extra_damping * delta_time)
            
            # Apply cutoff threshold
            if new_intensity < cutoff_threshold and target_intensity == 0.0:
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
        self.root.after(0, lambda: self.audio_level_var.set(0))
        self.root.after(0, lambda: self.smoothed_value_var.set(0))
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
                
                if self.verbose_logging.get():
                    self.logger.debug(f"Pattern - Type: {self.pattern_type}, Base: {base_value:.3f}, "
                                    f"Final: {self.pattern_current_intensity:.3f}")
                
                # Update UI
                pattern_percentage = self.pattern_current_intensity * 100
                self.root.after(0, lambda: self.pattern_level_var.set(pattern_percentage))
                
                # Send to device with rate limiting
                send_interval = 1.0 / self.update_rate
                should_send = (self.device and self.pattern_enabled and 
                             current_time - last_send_time >= send_interval)
                
                if should_send:
                    if self.verbose_logging.get():
                        self.logger.debug(f"Sending pattern to device - Intensity: {self.pattern_current_intensity:.4f}")
                    
                    self.root.after(0, self.update_device_from_pattern)
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
        """Audio processing worker thread"""
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
                
                # Calculate RMS (Root Mean Square) for volume level
                rms = np.sqrt(np.mean(audio_data**2))
                
                # More conservative sensitivity calculation
                sensitivity_factor = float(self.sensitivity.get()) / 100.0
                raw_volume = min(100.0, float(rms) * 500.0 * sensitivity_factor)
                
                # Convert to 0-1 range
                target_intensity = raw_volume / 100.0
                
                # Apply noise floor
                if target_intensity < noise_floor:
                    target_intensity = 0.0
                
                # Apply smoothing
                smoothed_intensity = self.apply_audio_smoothing(
                    smoothed_intensity, target_intensity, delta_time
                )
                
                # Cap the intensity at a reasonable maximum
                self.audio_intensity = float(min(0.8, smoothed_intensity))  # Cap at 80% max
                
                # Reduced logging - only log every 200 iterations and only if verbose logging is enabled
                log_counter += 1
                if self.verbose_logging.get() and log_counter % 200 == 0:
                    self.logger.debug(f"Audio - RMS: {rms:.4f}, Raw: {raw_volume:.1f}%, "
                                    f"Target: {target_intensity:.3f}, Smoothed: {self.audio_intensity:.3f}")
                
                # Update UI (show raw volume for visual feedback)
                self.root.after(0, lambda: self.audio_level_var.set(raw_volume))
                
                # Update smoothed value indicator
                smoothed_percentage = self.audio_intensity * 100
                self.root.after(0, lambda: self.smoothed_value_var.set(smoothed_percentage))
                
                # Send to device with configurable rate limiting (5 commands/sec)
                send_interval = 1.0 / self.update_rate  # 0.2 seconds for 5 commands/sec
                should_send = (self.device and self.audio_enabled and 
                             current_time - last_send_time >= send_interval)
                
                if should_send and (self.audio_intensity > 0.0 or 
                   (hasattr(self, '_last_sent_intensity') and self._last_sent_intensity > 0.0)):
                    
                    if self.verbose_logging.get():
                        self.logger.debug(f"Sending to device - Intensity: {self.audio_intensity:.4f}")
                    
                    self.root.after(0, self.update_device_from_audio)
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
        
    def on_pattern_type_changed(self, event=None):
        """Handle pattern type selection change"""
        self.pattern_type = self.pattern_type_var.get()
        self.logger.info(f"Pattern type changed to: {self.pattern_type}")
        # Reset pattern time when changing type for immediate effect
        self.pattern_time = 0.0
        
    def on_smoothing_type_changed(self, event=None):
        """Handle smoothing type selection change"""
        self.smoothing_type = self.smoothing_type_var.get()
        self.update_smoothing_description()
        self.logger.info(f"Smoothing type changed to: {self.smoothing_type}")
        
    def update_smoothing_description(self):
        """Update the smoothing type description"""
        descriptions = {
            "none": "No smoothing - instant response",
            "simple": "Gentle exponential smoothing",
            "adaptive": "Quick up, controlled down",
            "momentum": "Physics simulation (experimental)"
        }
        if hasattr(self, 'smoothing_desc_var'):
            self.smoothing_desc_var.set(descriptions.get(self.smoothing_type, ""))
            
    def apply_preset(self, preset_name):
        """Apply smoothing presets for common use cases"""
        presets = {
            "responsive": {
                "type": "adaptive",
                "attack": 0.02,
                "decay": 0.05,
                "strength": 0.2
            },
            "smooth": {
                "type": "simple", 
                "attack": 0.1,
                "decay": 0.3,
                "strength": 0.6
            },
            "bouncy": {
                "type": "momentum",
                "attack": 0.05,
                "decay": 0.2,
                "strength": 0.4
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            
            # Update values
            self.smoothing_type = preset["type"]
            self.attack_time = preset["attack"] 
            self.decay_time = preset["decay"]
            self.smoothing_strength = preset["strength"]
            
            # Update UI controls
            if hasattr(self, 'smoothing_type_var'):
                self.smoothing_type_var.set(self.smoothing_type)
                self.attack_time_var.set(self.attack_time * 100)
                self.decay_time_var.set(self.decay_time * 100)
                self.smoothing_strength_var.set(self.smoothing_strength * 100)
                
                # Update labels
                self.attack_time_label.config(text=f"{self.attack_time:.3f}s")
                self.decay_time_label.config(text=f"{self.decay_time:.3f}s") 
                self.smoothing_strength_label.config(text=f"{int(self.smoothing_strength * 100)}%")
                self.update_smoothing_description()
                
            self.logger.info(f"Applied '{preset_name}' preset")
        
    def on_smoothing_strength_changed(self, value):
        """Handle smoothing strength slider change"""
        self.smoothing_strength = float(value) / 100.0
        self.smoothing_strength_label.config(text=f"{int(float(value))}%")
        if self.verbose_logging.get():
            self.logger.debug(f"Smoothing strength changed to: {self.smoothing_strength:.2f}")
        
    def on_attack_time_changed(self, value):
        """Handle attack time slider change"""
        self.attack_time = float(value) / 100.0  # Convert back from UI scale (1-100 -> 0.01-1.0)
        self.attack_time_label.config(text=f"{self.attack_time:.3f}s")
        if self.verbose_logging.get():
            self.logger.debug(f"Attack time changed to: {self.attack_time:.3f}s")
        
    def on_decay_time_changed(self, value):
        """Handle decay time slider change"""
        self.decay_time = float(value) / 100.0  # Convert back from UI scale (1-100 -> 0.01-1.0)
        self.decay_time_label.config(text=f"{self.decay_time:.3f}s")
        if self.verbose_logging.get():
            self.logger.debug(f"Decay time changed to: {self.decay_time:.3f}s")
        
    def on_closing(self):
        """Handle application closing"""
        self.running = False
        
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
    except ImportError as e:
        print("Missing required packages. Please install:")
        print("pip install pyaudio numpy")
        print(f"Error: {e}")
        return
        
    root = tk.Tk()
    app = MuchFunApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()