import subprocess
import os
import time
import socket
import platform
import tkinter as tk
import threading
import json
from datetime import datetime

class RDPServer:
    def __init__(self, port=55000):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
    def start(self):
        try:
            self.sock.bind(('', self.port))
            self.sock.listen(1)
            print(f"Listening for RDP requests on port {self.port}")
            while True:
                client, addr = self.sock.accept()
                threading.Thread(target=self.handle_client, args=(client, addr)).start()
        except Exception as e:
            print(f"Server error: {e}")
            
    def handle_client(self, client, addr):
        try:
            data = client.recv(1024).decode()
            request = json.loads(data)
            response = self.show_consent_dialog(request['requester_name'])
            client.send(json.dumps({
                'approved': response,
                'timestamp': datetime.now().isoformat()
            }).encode())
            
            if response:
                self.start_rdp_listener()
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client.close()
            
    def show_consent_dialog(self, requester_name):
        def on_response(response):
            self.dialog_response = response
            self.popup.quit()
            
        self.dialog_response = False
        self.popup = tk.Tk()
        self.popup.title("Remote Connection Request")
        
        window_width = 300
        window_height = 150
        screen_width = self.popup.winfo_screenwidth()
        screen_height = self.popup.winfo_screenheight()
        x = (screen_width/2) - (window_width/2)
        y = (screen_height/2) - (window_height/2)
        self.popup.geometry(f'{window_width}x{window_height}+{int(x)}+{int(y)}')
        
        label = tk.Label(self.popup, 
                        text=f"{requester_name} wants to\nconnect to your computer via Remote Desktop.\n\nAllow connection?",
                        justify=tk.CENTER,
                        pady=10)
        label.pack()
        
        btn_frame = tk.Frame(self.popup)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, 
                 text="Allow", 
                 command=lambda: on_response(True),
                 bg='green',
                 fg='white',
                 width=10).pack(side=tk.LEFT, padx=5)
                 
        tk.Button(btn_frame,
                 text="Deny",
                 command=lambda: on_response(False),
                 bg='red',
                 fg='white',
                 width=10).pack(side=tk.LEFT, padx=5)
        
        self.popup.mainloop()
        self.popup.destroy()
        return self.dialog_response
        
    def start_rdp_listener(self):
        if platform.system() == 'Windows':
            subprocess.run(['powershell', 'Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0'])
            subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                          'name="Temporary RDP"',
                          'dir=in',
                          'action=allow',
                          'protocol=TCP',
                          'localport=3389'])

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def is_windows_device(ip):
    """Check if a device is running Windows by testing RDP port"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.1)
        result = s.connect_ex((ip, 3389)) == 0
        s.close()
        return result
    except:
        return False

def scan_network(windows_only=False):
    """Scan the local network for devices using Windows commands"""
    devices = []
    try:
        # Get ARP table
        arp_result = subprocess.check_output('arp -a', shell=True).decode()
        lines = arp_result.split('\n')
        
        print("\nScanning network... Please wait...")
        total_devices = sum(1 for line in lines if 'dynamic' in line.lower())
        scanned_devices = 0
        
        for line in lines:
            if 'dynamic' in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    mac = parts[1]
                    
                    # Update progress
                    scanned_devices += 1
                    clear_screen()
                    print(f"Scanning progress: {scanned_devices}/{total_devices} devices")
                    print(f"Currently scanning: {ip}")
                    
                    # Check if it's a Windows device
                    is_windows = is_windows_device(ip)
                    if not windows_only or (windows_only and is_windows):
                        try:
                            hostname = socket.gethostbyaddr(ip)[0]
                        except:
                            hostname = "Unknown"
                        
                        devices.append({
                            "ip": ip,
                            "mac": mac,
                            "hostname": hostname,
                            "os": "Windows" if is_windows else "Unknown"
                        })
    except Exception as e:
        print(f"Error scanning network: {e}")
    
    return devices

def request_rdp_access(target_ip, requester_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((target_ip, 55000))
        
        request = {
            'requester_name': requester_name,
            'timestamp': datetime.now().isoformat()
        }
        sock.send(json.dumps(request).encode())
        
        response = json.loads(sock.recv(1024).decode())
        
        if response['approved']:
            print("Connection approved! Starting RDP connection...")
            if platform.system() == 'Windows':
                subprocess.Popen(['mstsc', f'/v:{target_ip}'])
        else:
            print("Connection request was denied by the user.")
            
    except Exception as e:
        print(f"Error requesting RDP access: {e}")
    finally:
        sock.close()

def main():
    if platform.system() == 'Windows':
        rdp_server = RDPServer()
        threading.Thread(target=rdp_server.start, daemon=True).start()
    
    clear_screen()
    print("╔══════════════════════════════════════╗")
    print("║        Network Scanner v1.0           ║")
    print("╚══════════════════════════════════════╝")
    print(f"\nYour IP address: {get_local_ip()}")
    
    # Ask for scan type
    while True:
        print("\nScan type:")
        print("1: Scan for Windows devices only")
        print("2: Scan for all devices")
        try:
            scan_type = int(input("\nEnter your choice (1-2): "))
            if scan_type in [1, 2]:
                break
            else:
                clear_screen()
                print("Please enter 1 or 2")
        except ValueError:
            clear_screen()
            print("Please enter a valid number")
    
    windows_only = (scan_type == 1)
    devices = scan_network(windows_only)
    
    while True:
        clear_screen()
        print("╔══════════════════════════════════════╗")
        print("║        Network Scanner v1.0           ║")
        print("╚══════════════════════════════════════╝")
        print(f"\nYour IP address: {get_local_ip()}")
        print(f"\nScanning mode: {'Windows devices only' if windows_only else 'All devices'}")
        
        if devices:
            print("\nDiscovered Devices:")
            print("═" * 70)
            print(f"{'#':<3} {'IP Address':<15} {'Hostname':<30} {'OS':<10}")
            print("═" * 70)
            
            for idx, device in enumerate(devices, 1):
                print(f"{idx:<3} {device['ip']:<15} {device['hostname'][:30]:<30} {device['os']:<10}")
        else:
            print("\nNo devices found.")
        
        print("\nOptions:")
        print("╔══════════════════╗")
        print("║ 1: Refresh scan  ║")
        print("║ 2: RDP Connect   ║")
        print("║ 3: Change mode   ║")
        print("║ 4: Exit          ║")
        print("╚══════════════════╝")
        
        try:
            choice = int(input("\nSelect an option: "))
            if choice == 1:
                clear_screen()
                print("Initiating new scan...")
                devices = scan_network(windows_only)
            elif choice == 2:
                if not devices:
                    print("No devices to connect to!")
                    time.sleep(2)
                    continue
                    
                device_num = int(input("Enter device number to connect to: ")) - 1
                if 0 <= device_num < len(devices):
                    target_device = devices[device_num]
                    if target_device['os'] == 'Windows':
                        your_name = input("Enter your device name (will be shown to target user): ")
                        print(f"Requesting connection to {target_device['hostname']}...")
                        request_rdp_access(target_device['ip'], your_name)
                    else:
                        print("RDP is only available for Windows devices.")
                        time.sleep(2)
                else:
                    print("Invalid device number")
                    time.sleep(2)
            elif choice == 3:
                windows_only = not windows_only
                clear_screen()
                print(f"Switched to {'Windows only' if windows_only else 'All devices'} mode")
                print("Initiating new scan...")
                devices = scan_network(windows_only)
            elif choice == 4:
                break
        except ValueError:
            print("Please enter a valid option")
            time.sleep(2)

if __name__ == "__main__":
    main()
