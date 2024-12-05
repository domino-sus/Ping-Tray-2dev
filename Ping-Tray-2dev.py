import pystray
from PIL import Image, ImageDraw
import threading
import subprocess
import time
import platform
from typing import Tuple, List, Dict
from collections import deque
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
# Configure default matplotlib style
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--'
})

class NetworkMonitor:
    def __init__(self):
        # Device configuration
        self.ip1 = "192.168.0.1"
        self.ip2 = "192.168.0.2"
        
        # Monitor settings
        self.ping_timeout = 1  # seconds
        self.ping_retries = 2  # number of retries
        self.check_interval = 5  # seconds between checks
        
        self.running = True
        self.device1_status = False
        self.device2_status = False
        self.icon = None
        self.icon_size = (32, 32)

        # Initialize history storage (24 hours of data)
        max_history = int(24 * 3600 / self.check_interval)
        self.history: Dict[str, deque] = {
            'timestamps': deque(maxlen=max_history),
            'device1': deque(maxlen=max_history),
            'device2': deque(maxlen=max_history),
            'status_changes': deque(maxlen=100)  # Store last 100 status changes
        }

    def create_icon(self) -> Image.Image:
        """Create a split square icon with status colors"""
        image = Image.new('RGB', self.icon_size, 'white')
        draw = ImageDraw.Draw(image)

        # Left half (first device)
        color1 = 'green' if self.device1_status else 'red'
        draw.rectangle([0, 0, self.icon_size[0]//2, self.icon_size[1]], fill=color1)

        # Right half (second device)
        color2 = 'green' if self.device2_status else 'red'
        draw.rectangle([self.icon_size[0]//2, 0, self.icon_size[0], self.icon_size[1]], fill=color2)

        return image

    def ping(self, ip: str) -> bool:
        """Ping an IP address and return True if reachable"""
        # Get the correct ping command path based on platform
        if platform.system().lower() == 'windows':
            ping_cmd = 'C:\\Windows\\System32\\ping.exe'
            param = '-n'
            timeout_param = '-w'
        else:
            ping_cmd = 'ping'  # Use ping directly from PATH
            param = '-c'
            timeout_param = '-W'

        for attempt in range(self.ping_retries):
            try:
                command = [ping_cmd, param, '1', timeout_param, str(self.ping_timeout), ip]

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                stdout, stderr = process.communicate(timeout=self.ping_timeout + 1)

                if process.returncode == 0:
                    return True

            except subprocess.TimeoutExpired:
                print(f"Ping timeout for {ip} on attempt {attempt + 1}")
                process.kill()
            except subprocess.SubprocessError as e:
                print(f"Ping error for {ip} on attempt {attempt + 1}: {str(e)}")
            except Exception as e:
                print(f"Unexpected error while pinging {ip} on attempt {attempt + 1}: {str(e)}")

            time.sleep(0.5)  # Short delay between retries

        return False

    def update_status(self) -> None:
        """Update the status of both devices"""
        old_status = (self.device1_status, self.device2_status)

        self.device1_status = self.ping(self.ip1)
        self.device2_status = self.ping(self.ip2)

        current_time = datetime.now()

        # Update history
        self.history['timestamps'].append(current_time)
        self.history['device1'].append(1 if self.device1_status else 0)
        self.history['device2'].append(1 if self.device2_status else 0)
        
        # Print debug information
        print(f"Updated status at {current_time}: Device1={self.device1_status}, Device2={self.device2_status}")
        print(f"History lengths: timestamps={len(self.history['timestamps'])}, device1={len(self.history['device1'])}, device2={len(self.history['device2'])}")

        # Record status changes
        if (self.device1_status, self.device2_status) != old_status:
            change_record = {
                'time': current_time,
                'device1': {'old': old_status[0], 'new': self.device1_status},
                'device2': {'old': old_status[1], 'new': self.device2_status}
            }
            self.history['status_changes'].append(change_record)

        if self.icon:
            self.icon.icon = self.create_icon()
            self.icon.title = self.get_status_text()

            # Notify on status change
            if (self.device1_status, self.device2_status) != old_status:
                self.icon.notify(
                    title="Network Status Change",
                    message=self.get_status_text()
                )

    def show_status_window(self) -> None:
        """Create and show the status window with historical graph and status changes"""
        # Create main window as Toplevel instead of Tk
        window = tk.Toplevel()
        window.title("Network Status History")
        window.geometry("1200x800")
        
        # Create root window if it doesn't exist
        if not hasattr(self, 'root'):
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the root window

        # Create notebook for tabs
        notebook = ttk.Notebook(window)  # Using ttk.Notebook from properly imported ttk
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Graph tab
        graph_frame = tk.Frame(notebook)
        notebook.add(graph_frame, text="Status Graph")

        # Create matplotlib figure with custom style
        fig = Figure(figsize=(12, 6), dpi=100)
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor('#F0F0F0')
        ax.set_facecolor('#FFFFFF')
        ax.grid(True, linestyle='--', alpha=0.3)

        # Convert data for plotting
        times = list(self.history['timestamps'])
        device1_status = list(self.history['device1'])
        device2_status = list(self.history['device2'])

        if times:
            # Convert times to numbers for plotting
            times_num = mdates.date2num(times)
            
            # Plot device status lines
            ax.step(times_num, device1_status, where='post', color='green', 
                   label=f'Device 1 ({self.ip1})', linewidth=2, alpha=0.7)
            ax.step(times_num, device2_status, where='post', color='blue',
                   label=f'Device 2 ({self.ip2})', linewidth=2, alpha=0.7)

            # Set x-axis to start from 00:00 and show full 24 hours
            current_time = datetime.now()
            end_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            start_time = end_time - timedelta(days=1)
            
            # Always show full 24 hours range starting from 00:00
            ax.set_xlim(start_time, end_time)
            
            # Format x-axis with ticks every 15 minutes
            major_locator = mdates.HourLocator(interval=1)  # Major ticks every hour
            minor_locator = mdates.MinuteLocator(byminute=[0, 15, 30, 45])  # Minor ticks every 15 minutes
            hours_fmt = mdates.DateFormatter('%H:%M')  # Show hours and minutes
            
            ax.xaxis.set_major_locator(major_locator)
            ax.xaxis.set_minor_locator(minor_locator)
            ax.xaxis.set_major_formatter(hours_fmt)
            
            # Customize x-axis labels with smaller font and better spacing
            plt.setp(ax.xaxis.get_majorticklabels(), 
                    rotation=45,  # Rotate labels for better spacing
                    ha='right',   # Align to right
                    fontsize=8)   # Smaller font size
            
            # Enhance grid appearance
            ax.grid(True, which='major', linestyle='-', alpha=0.2)
            ax.grid(True, which='minor', linestyle=':', alpha=0.1)
            
            # Adjust figure size and layout for better visibility
            fig.set_size_inches(14, 6)  # Make figure wider
            plt.subplots_adjust(bottom=0.15)  # Add more space for x-axis labels

            # Customize appearance
            ax.set_ylim(-0.1, 1.1)
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Offline', 'Online'])
            ax.grid(True, which='major', linestyle='--', alpha=0.3)
            ax.grid(True, which='minor', linestyle=':', alpha=0.1)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Add title with modern styling
            ax.set_title('Network Device Status Timeline', 
                        fontsize=16, pad=20, color='#333333')
            ax.set_xlabel('Time (Last 24 Hours)', fontsize=12, labelpad=10, color='#666666')

            # Add legend
            ax.legend(loc='upper right', fancybox=True, shadow=True)

        # Create canvas and add to window
        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status changes tab
        changes_frame = tk.Frame(notebook)
        notebook.add(changes_frame, text="Status Changes")

        # Create text widget for status changes
        changes_text = tk.Text(changes_frame, wrap=tk.WORD, height=20)
        scrollbar = tk.Scrollbar(changes_frame, command=changes_text.yview)
        changes_text.configure(yscrollcommand=scrollbar.set)

        changes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add status changes to text widget with improved styling
        changes_text.tag_configure('header', font=('Helvetica', 11, 'bold'))
        changes_text.tag_configure('online', foreground='#2ECC71', font=('Helvetica', 10))
        changes_text.tag_configure('offline', foreground='#E74C3C', font=('Helvetica', 10))
        changes_text.tag_configure('time', font=('Courier', 10))

        changes_text.insert(tk.END, "Recent Status Changes:\n\n", 'header')

        for change in reversed(self.history['status_changes']):
            time_str = change['time'].strftime('%Y-%m-%d %H:%M:%S')
            changes_text.insert(tk.END, f"➤ {time_str}\n", 'time')

            if change['device1']['old'] != change['device1']['new']:
                status = "Online" if change['device1']['new'] else "Offline"
                tag = 'online' if change['device1']['new'] else 'offline'
                changes_text.insert(tk.END, f"   Device 1 ({self.ip1}): Changed to {status}\n", tag)

            if change['device2']['old'] != change['device2']['new']:
                status = "Online" if change['device2']['new'] else "Offline"
                tag = 'online' if change['device2']['new'] else 'offline'
                changes_text.insert(tk.END, f"   Device 2 ({self.ip2}): Changed to {status}\n", tag)

            changes_text.insert(tk.END, "\n")

        changes_text.configure(state='disabled')

        # Add close button with modern styling
        close_button = tk.Button(
            window,
            text="Close",
            command=window.destroy,
            relief=tk.FLAT,
            bg='#3498db',
            fg='white',
            padx=20,
            pady=10,
            font=('Helvetica', 10)
        )
        close_button.pack(pady=10)

        # Start the window's main loop
        window.mainloop()

    def monitor_thread(self):
        """Start the monitoring process in a separate thread"""
        while self.running:
            self.update_status()  # Check the devices' status
            time.sleep(self.check_interval)  # Wait for the next check interval

    def get_status_text(self) -> str:
        """Get current status text for both devices"""
        status1 = "Online" if self.device1_status else "Offline"
        status2 = "Online" if self.device2_status else "Offline"
        return f"Device 1 ({self.ip1}): {status1}\nDevice 2 ({self.ip2}): {status2}"

    def on_clicked(self, icon, item) -> None:
        """Handle menu item clicks"""
        if item.text == "Status":
            self.show_status_window()
        elif item.text == "Exit":
            self.running = False
            if hasattr(self, 'root'):
                self.root.quit()
            if self.icon:
                self.icon.stop()

    def run(self) -> None:
        """Main application entry point"""
        try:
            # Initialize root window and hide it
            self.root = tk.Tk()
            self.root.withdraw()
            
            # Create initial icon
            icon_image = self.create_icon()

            # Create system tray icon with status tooltip
            self.icon = pystray.Icon(
                "network_monitor",
                icon_image,
                self.get_status_text(),  # Set initial tooltip
                menu=pystray.Menu(
                    pystray.MenuItem("Status", self.on_clicked),
                    pystray.MenuItem("Exit", self.on_clicked)
                )
            )

            # Start monitoring thread
            monitor_thread = threading.Thread(target=self.monitor_thread, daemon=True)
            monitor_thread.start()

            # Run the system tray icon
            self.icon.run()

        except Exception as e:
            print(f"Error starting network monitor: {str(e)}")

if __name__ == "__main__":
    monitor = NetworkMonitor()
    monitor.run()