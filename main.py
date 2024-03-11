from flask import Flask, render_template, request, jsonify
from threading import Thread
import subprocess
import psutil

app = Flask(__name__)

username = "username"
password = "password"
camera_process = None
status = False

def run_camera_command():
    global camera_process, status
    cmd = f"rpicam-vid -n -p 0,0,640,480 --framerate 24 -t 0 --inline -o - | cvlc -vvv stream:///dev/stdin --sout '#rtp{{sdp=rtsp://:8554/stream}}' :demux=h264 :network-caching=50 :h264-fps=24 --sout-rtsp-user {username} --sout-rtsp-pwd {password}"
    camera_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    status = True


@app.route('/status', methods=['GET'])
def get_status():
    global status
    # print(status)
    return jsonify({"status": status})


def stop_camera_command():
    global camera_process, status
    if camera_process:
        parent_pid = camera_process.pid  
        parent = psutil.Process(parent_pid)  
        for child in parent.children(recursive=True):  
            child.kill()
        parent.kill()
        camera_process.wait()
        camera_process = None
        status = False


def start_camera_command():
    global camera_process, status
    if camera_process is None:
        Thread(target=run_camera_command).start()
        status = True
        return jsonify({"message": "Camera started successfully"})
    return jsonify({"message": "Camera already running"})


@app.route('/', methods=['GET', 'POST', 'PUT'])
def index():
    global username, password, status
    if request.method == 'POST' or request.method == 'PUT':
        data = request.json
        username = data.get('username', username)
        password = data.get('password', password)
        stop_camera_command()
        start_camera_command()
        return jsonify({"message": "Credentials updated successfully", "status": status, "username": username, "password": password})
    return render_template('index.html', status=status, username=username, password=password)


@app.route('/stop', methods=['GET'])
def stop_camera():
    stop_camera_command()
    return jsonify({"message": "Camera stopped successfully"})


@app.route('/start', methods=['GET'])
def start_camera():
    return start_camera_command()


if __name__ == "__main__":
    try:
        Thread(target=run_camera_command).start()
        app.run("0.0.0.0", "5000", False)
    except KeyboardInterrupt:
        stop_camera_command()
        print("Exiting...")
