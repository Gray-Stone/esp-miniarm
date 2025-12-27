# main.py — ESP32-C3 (MicroPython 官方固件)
# 仅在 STA 模式启用内置 mDNS（若可用），广播 esp-miniarm.local

import network
import socket
import ujson
import utime
import machine
import uos
import gc
import ubinascii

# ==================== 网页模板 ====================
WEB_CONFIG = """
<!DOCTYPE html>
<html>
<head>
    <title>Robot Arm Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        input, button { margin: 5px; padding: 10px; }
        .container { max-width: 400px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WiFi Configuration</h1>
        <form id="configForm">
            <div>
                <label>SSID:</label><br>
                <input type="text" id="ssid" name="ssid" required>
            </div>
            <div>
                <label>Password:</label><br>
                <input type="password" id="password" name="password">
            </div>
            <button type="submit">Save & Reboot</button>
        </form>
        <p>Current IP: <span id="ip"></span></p>
    </div>
    <script>
        document.getElementById('ip').textContent = window.location.hostname;
        document.getElementById('configForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = {
                ssid: document.getElementById('ssid').value,
                password: document.getElementById('password').value
            };
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(formData)
                });
                const result = await response.json();
                alert(result.message);
                if (result.status === 'success') {
                    setTimeout(() => { location.reload(); }, 2000);
                }
            } catch (error) {
                alert('Configuration failed: ' + error);
            }
        });
    </script>
</body>
</html>
"""

WEB_CONTROL = """
<!DOCTYPE html>
<html>
<head>
    <title>Robot Arm Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        button { 
            margin: 10px; 
            padding: 15px 25px; 
            font-size: 16px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        .nav { margin: 20px 0; }
        .nav a { margin: 0 10px; color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>Robot Arm Control</h1>
    <div>
        <button onclick="executeProgram(1)">Program 1: Pick and Place</button><br>
        <button onclick="executeProgram(2)">Program 2: Custom Routine</button><br>
        <button onclick="executeProgram(3)">Program 3: Test Sequence</button><br>
        <button onclick="executeProgram(4)" style="background: #dc3545;">Emergency Stop</button>
    </div>
    <div class="nav">
        <hr>
        <a href="/config">WiFi Configuration</a> | 
        <a href="/">Control Panel</a> | 
        <a href="/system">System Info</a>
    </div>
    <div id="status"></div>
    <p>Try: <code>http://esp-miniarm.local</code></p>
    <script>
        async function executeProgram(programId) {
            const status = document.getElementById('status');
            status.innerHTML = 'Executing program ' + programId + '...';
            status.style.color = 'blue';
            try {
                const response = await fetch('/api/execute?program=' + programId);
                const result = await response.json();
                status.innerHTML = result.message;
                status.style.color = result.status === 'success' ? 'green' : 'red';
            } catch (error) {
                status.innerHTML = 'Execution failed: ' + error;
                status.style.color = 'red';
            }
        }
    </script>
</body>
</html>
"""

WEB_SYSTEM_INFO = """
<!DOCTYPE html>
<html>
<head>
    <title>System Information</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .info { margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px; }
        .nav { margin: 20px 0; }
        .nav a { margin: 0 10px; color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>System Information</h1>
    <div class="info">
        <strong>Device ID:</strong> <span id="deviceId">Loading...</span>
    </div>
    <div class="info">
        <strong>Free Memory:</strong> <span id="freeMem">Loading...</span>
    </div>
    <div class="info">
        <strong>Storage:</strong> <span id="storage">Loading...</span>
    </div>
    <div class="info">
        <strong>Uptime:</strong> <span id="uptime">Loading...</span>
    </div>
    <div class="nav">
        <hr>
        <a href="/">Control Panel</a> | 
        <a href="/config">WiFi Configuration</a>
    </div>
    <script>
        async function loadSystemInfo() {
            try {
                const response = await fetch('/api/system');
                const data = await response.json();
                document.getElementById('deviceId').textContent = data.device_id;
                document.getElementById('freeMem').textContent = data.free_memory + ' bytes';
                document.getElementById('storage').textContent = data.storage;
                document.getElementById('uptime').textContent = data.uptime + ' seconds';
            } catch (error) {
                document.getElementById('deviceId').textContent = 'Error loading info';
            }
        }
        loadSystemInfo();
        setInterval(loadSystemInfo, 10000);
    </script>
</body>
</html>
"""


# ==================== 配置管理 ====================
def load_config():
    try:
        with open('config.json', 'r') as f:
            return ujson.load(f)
    except:
        return {"ssid": "", "password": ""}


def save_config(ssid, password):
    config = {"ssid": ssid, "password": password}
    with open('config.json', 'w') as f:
        ujson.dump(config, f)


# ==================== 网络连接 ====================
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # 提前设置我们希望的主机名（有的固件需要在连接前设置）
    try:
        wlan.config(hostname="esp-miniarm")
        print("Set STA hostname=esp-miniarm")
    except Exception:
        try:
            wlan.config(dhcp_hostname="esp-miniarm")
            print("Set STA dhcp_hostname=esp-miniarm")
        except Exception:
            pass

    config = load_config()
    if config["ssid"]:
        print("Connecting to WiFi:", config["ssid"])
        wlan.connect(config["ssid"], config["password"] or None)

        for _ in range(20):  # 最多等 20 秒
            if wlan.isconnected():
                print("Connected! IP:", wlan.ifconfig()[0])
                return wlan, True
            utime.sleep(1)

    return wlan, False


def start_ap_mode():
    # AP 模式不启用 mDNS（按你的要求）
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="RoboticArm_AP", password="12345678", authmode=network.AUTH_WPA_WPA2_PSK)
    print("AP Mode. Connect to: RoboticArm_AP")
    print("AP IP:", ap.ifconfig()[0])
    return ap


def setup_network():
    wlan, connected = connect_wifi()
    if not connected:
        print("Starting AP mode for configuration")
        ap = start_ap_mode()
        return ap, True  # 返回 AP 接口与“AP 模式标志”
    return wlan, False  # 返回 STA 接口与“非 AP 模式标志”


# ==================== 仅在 STA 模式尝试启用内置 mDNS ====================
def try_start_builtin_mdns(hostname: str, wlan_iface):
    """
    优先使用固件自带 mdns 模块；若不可用，至少确保 hostname 已设置。
    成功返回 True；否则 False。
    """
    ok = False

    # 再尝试设置一次主机名（不同固件可能需要在连上网后设置才生效）
    for key in ("hostname", "dhcp_hostname"):
        try:
            wlan_iface.config(**{key: hostname})
            print("[mDNS] set", key, "=", hostname)
            ok = True
        except Exception:
            pass

    # 若有内置 mdns 模块，注册服务
    try:
        import mdns  # 部分官方固件提供
        # 可能存在类 Server 的实现
        try:
            srv = mdns.Server(wlan_iface)
            if hasattr(srv, "set_hostname"):
                srv.set_hostname(hostname)
            if hasattr(srv, "set_instance_name"):
                srv.set_instance_name(hostname)
            if hasattr(srv, "add_service"):
                srv.add_service("_http", "_tcp", 80, txt={"path": "/"})
            print("[mDNS] builtin mdns.Server started as %s.local" % hostname)
            return True
        except Exception:
            # 也可能是函数式 API
            if hasattr(mdns, "start"):
                try:
                    mdns.start(hostname=hostname, instance_name=hostname)
                except TypeError:
                    # 兼容某些签名
                    mdns.start(hostname)
                if hasattr(mdns, "add_service"):
                    try:
                        mdns.add_service("_http", "_tcp", 80, txt={"path": "/"})
                    except TypeError:
                        mdns.add_service("_http", "_tcp", 80)
                print("[mDNS] builtin mdns started as %s.local" % hostname)
                return True
    except Exception:
        # 没有 mdns 模块也不报错，ok 依旧表示 hostname 已尽力设置
        pass

    return ok


# ==================== 机械臂控制 ====================
class RoboticArm:

    def __init__(self):
        print("RoboticArm initialized")

    def move_to_position(self, position):
        print("Moving to position:", position)

    def emergency_stop(self):
        print("EMERGENCY STOP ACTIVATED!")


arm = RoboticArm()


def execute_program(program_id):
    try:
        if program_id == 1:
            arm.move_to_position("pickup")
            return "Program 1 completed successfully"
        elif program_id == 2:
            arm.move_to_position("position1")
            return "Program 2 completed successfully"
        elif program_id == 3:
            arm.move_to_position("123123")
            return "Program 3 completed successfully"
        elif program_id == 4:
            arm.emergency_stop()
            return "EMERGENCY STOP activated"
        else:
            return "Unknown program ID: %s" % program_id
    except Exception as e:
        return "Error executing program: %s" % str(e)


# ==================== Web服务器 ====================
class WebServer:

    def __init__(self):
        self.ap_mode = False
        self.wlan, self.ap_mode = setup_network()
        self.start_time = utime.time()

    def get_uptime(self):
        return utime.time() - self.start_time

    def get_system_info(self):
        try:
            device_id = ubinascii.hexlify(machine.unique_id()).decode()
        except:
            device_id = "unknown"
        free_mem = gc.mem_free()
        try:
            fs_stat = uos.statvfs('/')
            block_size = fs_stat[0]
            total_blocks = fs_stat[2]
            free_blocks = fs_stat[3]
            total_size = (block_size * total_blocks) // 1024
            free_size = (block_size * free_blocks) // 1024
            storage_info = "%dKB free / %dKB total" % (free_size, total_size)
        except:
            storage_info = "unknown"
        return {
            "device_id": device_id,
            "free_memory": free_mem,
            "storage": storage_info,
            "uptime": int(self.get_uptime())
        }

    def parse_request(self, request):
        lines = request.split('\r\n')
        if lines:
            first_line = lines[0].split(' ')
            if len(first_line) > 1:
                method = first_line[0]
                path = first_line[1].split('?')[0]
                return method, path
        return None, None

    def handle_request(self, client_socket, addr):
        try:
            request = client_socket.recv(1024).decode('utf-8')
            if not request:
                client_socket.close()
                return

            method, path = self.parse_request(request)
            print("Request:", method, path, "from", addr)

            if method == 'GET':
                if path == '/' or path == '/control':
                    self.send_response(client_socket, WEB_CONTROL, 'text/html')
                elif path == '/config':
                    self.send_response(client_socket, WEB_CONFIG, 'text/html')
                elif path == '/system':
                    self.send_response(client_socket, WEB_SYSTEM_INFO, 'text/html')
                elif path == '/api/system':
                    info = self.get_system_info()
                    self.send_json_response(client_socket, info)
                elif path.startswith('/api/execute'):
                    self.handle_execute(client_socket, request)
                else:
                    self.send_response(client_socket, 'Not found', 'text/plain', 404)
            elif method == 'POST':
                if path == '/api/config':
                    self.handle_config(client_socket, request)
                else:
                    self.send_response(client_socket, 'Not found', 'text/plain', 404)
            else:
                self.send_response(client_socket, 'Method not allowed', 'text/plain', 405)
        except Exception as e:
            print("Error handling request:", e)
            try:
                self.send_response(client_socket, 'Error: %s' % str(e), 'text/plain', 500)
            except:
                client_socket.close()

    def handle_execute(self, client_socket, request):
        lines = request.split('\r\n')
        first_line = lines[0]
        if '?' in first_line:
            query_str = first_line.split('?')[1].split(' ')[0]
            params = {}
            for pair in query_str.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value
            try:
                program_id = int(params.get('program', 1))
            except:
                program_id = 1
            result = execute_program(program_id)
            response = {'status': 'success', 'message': result}
        else:
            response = {'status': 'error', 'message': 'No program specified'}
        self.send_json_response(client_socket, response)

    def handle_config(self, client_socket, request):
        try:
            content_length = 0
            lines = request.split('\r\n')
            for line in lines:
                if line.startswith('Content-Length:'):
                    content_length = int(line.split(':', 1)[1].strip())
                    break
            body = request.split('\r\n\r\n', 1)[1]
            if len(body) < content_length:
                remaining = content_length - len(body)
                body += client_socket.recv(remaining).decode('utf-8')
            data = ujson.loads(body)
            save_config(data.get('ssid', ''), data.get('password', ''))
            response = {'status': 'success', 'message': 'WiFi config saved. Device will reboot...'}
            self.send_json_response(client_socket, response)
            utime.sleep(2)
            machine.reset()
        except Exception as e:
            response = {'status': 'error', 'message': 'Config error: %s' % str(e)}
            self.send_json_response(client_socket, response)

    def send_response(self, client_socket, content, content_type='text/html', status_code=200):
        response = "HTTP/1.1 %d OK\r\n" % status_code
        response += "Content-Type: %s\r\n" % content_type
        response += "Connection: close\r\n\r\n"
        response += content
        client_socket.send(response.encode('utf-8'))
        client_socket.close()

    def send_json_response(self, client_socket, data):
        self.send_response(client_socket, ujson.dumps(data), 'application/json')

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except:
            pass
        server_socket.bind(('0.0.0.0', 80))
        server_socket.listen(5)

        print("Web server started on port 80")
        if self.ap_mode:
            print("AP Mode: Connect to 'RoboticArm_AP' with password '12345678'")
            print("Then visit: http://192.168.4.1")
        else:
            # 仅在 STA 模式启用 mDNS
            hostname = "esp-miniarm"
            print("STA Mode: Configuring mDNS for %s.local ..." % hostname)
            if try_start_builtin_mdns(hostname, self.wlan):
                print("mDNS ready (builtin): %s.local" % hostname)
            else:
                print("mDNS API not available; hostname set. Many stacks still resolve %s.local" % hostname)

        while True:
            try:
                client_socket, addr = server_socket.accept()
                self.handle_request(client_socket, addr)
            except Exception as e:
                print("Server error:", e)
                utime.sleep(1)


# ==================== 主程序 ====================
def main():
    gc.collect()
    print("Free memory:", gc.mem_free())
    server = WebServer()
    server.run()


if __name__ == "__main__":
    main()
