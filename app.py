from flask import Flask, Response, redirect, render_template, request, jsonify, send_from_directory, url_for
from threading import Thread
import subprocess
import psutil
import cv2
import os
from datetime import datetime, timedelta
from flask_cors import CORS
from cam import Camera

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
RECORDINGS_FOLDER = 'recordings'
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)

app = Flask(__name__)

username = "username"
password = "password"
camera_process = None
status = False
camera_processes = {}
continuous_record = False

def record_stream(camera: Camera):
    while True:
        if camera.recordConstant is False:
            print(f"Recording stopped for camera {camera.id}.")
            break

        print(f"Recording started for camera {camera.id}...")
        record_duration = 15
        
        filename = f"{RECORDINGS_FOLDER}/record_{camera.id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]}.avi"

        command = ['ffmpeg', '-i', camera.__str__(), '-t', str(record_duration), '-c:v', 'copy', filename]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        camera_processes[camera.id] = process
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Error occurred during recording for camera {camera.id}: {stderr.decode('utf-8')}")
        
        print(f"Recording duration exceeded for camera {camera.id}. Restarting recording...")
        record_stream(camera)
        


@app.route('/start_continuous_record/<int:camera_id>', methods=['GET'])
def start_continuous_record_route(camera_id):
    for camera in cameras:
        if camera.id == camera_id:
            camera = camera
            break
    if camera:
        global continuous_record
        # continuous_record = True
        camera.recordConstant = True
        Thread(target=record_stream, kwargs={'camera': camera}).start()
        return {"message": f"Continuous recording started successfully for camera {camera.id}"}
    else:
        return jsonify({"error": "Camera not found"}), 404


@app.route('/stop_continuous_record/<int:camera_id>', methods=['GET'])
def stop_continuous_record_route(camera_id):
    for camera in cameras:
        if camera.id == camera_id:
            camera = camera
            break
    if camera:
        process = camera_processes[camera_id]
        if process is None:
            return {"message": f"No active recording process found for camera {camera_id}"}
        global continuous_record
        camera.recordConstant = False
        # process.terminate()
        del camera_processes[camera_id]
        return {"message": f"Continuous recording stopped successfully for camera {camera_id}"}
    else:
        return jsonify({"error": "Camera not found"}), 404


def gen_frames(camera: Camera):
    app = camera.__str__()
    cap = cv2.VideoCapture(app, cv2.CAP_FFMPEG)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
            cv2.putText(frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                break
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed', methods=['GET'])
def video_feed():
    ip_address = request.args.get('ip')
    port = request.args.get('port')
    username = request.args.get('username')
    password = request.args.get('password')
    url = request.args.get('url')

    camera = Camera(ip=ip_address, port=port, username=username, password=password, url=url)

    gen = gen_frames(camera)

    return Response(gen, mimetype='multipart/x-mixed-replace; boundary=frame')

def run_camera_command():
    global camera_process, status
    cmd = f"rpicam-vid -n -p 0,0,640,480 --vflip --framerate 24 --bitrate 2000000 -t 0 --inline -o - | cvlc -vvv stream:///dev/stdin --sout '#rtp{{sdp=rtsp://:8554/stream}}' :demux=h264 :h264-fps=24 --sout-rtsp-user {username} --sout-rtsp-pwd {password}"
    camera_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    status = True


@app.route('/status', methods=['GET'])
def get_status():
    global status
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
@app.route('/index', methods=['GET', 'POST', 'PUT'])
@app.route('/newIndex', methods=['GET', 'POST', 'PUT'])
@app.route('/home', methods=['GET', 'POST', 'PUT'])
def index():
    # if url is /index direct to newIndex.html
    global username, password, status
    if request.path == '/newIndex':
        return render_template('newIndex.html')
    
    if request.method == 'POST' or request.method == 'PUT':
        data = request.json
        username = data.get('username', username)
        password = data.get('password', password)
        stop_camera_command()
        start_camera_command()
        return jsonify({"message": "Credentials updated successfully", "status": status, "username": username, "password": password})
    
    recordings = []
    for filename in os.listdir(RECORDINGS_FOLDER):
        filepath = os.path.join(RECORDINGS_FOLDER, filename)
        file_stat = os.stat(filepath)
        file_info = {
            'name': filename,
            'size': f"{file_stat.st_size / (1024 * 1024):.2} MB",
            'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S") # type: ignore
        }
        recordings.append(file_info)

    recordings = sorted(recordings, key=lambda x: x['created_at'], reverse=True)
    return render_template('newIndex.html', status=status, username=username, password=password, recordings=recordings, cameras=cameras, camera_count=len(cameras))

@app.route('/recordingList', methods=['GET', 'POST'])
def recording_list():
    recordings = []
    draw = request.form['draw'] 
    row = int(request.form['start'])
    rowperpage = int(request.form['length'])
    searchValue = request.form["search[value]"]

    for filename in os.listdir(RECORDINGS_FOLDER):
        filepath = os.path.join(RECORDINGS_FOLDER, filename)
        file_stat = os.stat(filepath)
        file_info = {
            'name': filename,
            'size': f"{file_stat.st_size / (1024 * 1024):.2f} MB",
            'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S.%f")[:-2] # type: ignore
        }
        recordings.append(file_info)

    total_count = len(recordings)

    if searchValue:
        recordings = [rec for rec in recordings if searchValue.lower() in rec['name'].lower()]

    recordings = sorted(recordings, key=lambda x: x['created_at'], reverse=True)
    recordings = recordings[row: row + rowperpage]

    response = {
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': recordings.length,
        'data': recordings,
    }

    return jsonify(response)

@app.route('/stop', methods=['GET'])
def stop_camera():
    stop_camera_command()
    return jsonify({"message": "Camera stopped successfully"})

@app.route('/start', methods=['GET'])
def start_camera():
    return start_camera_command()

@app.route('/recordings/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(RECORDINGS_FOLDER, filename, as_attachment=True)

cameras = []

@app.route('/add_camera', methods=['POST'])
def add_or_update_camera():
    global cameras
    data = request.json
    ip = data.get('ip')
    port = data.get('port')
    username = data.get('username')
    password = data.get('password')
    url = data.get('url')
    camera_id = data.get('id')

    if camera_id is not None and camera_id != "":
        camera_id = int(camera_id)
        if camera_id >= 0 and camera_id < len(cameras):
            cameras[camera_id].ip = ip
            cameras[camera_id].port = port
            cameras[camera_id].username = username
            cameras[camera_id].password = password
            cameras[camera_id].url = url
            return jsonify({"message": f"Camera updated successfully with id {camera_id}"}), 200
        else:
            return jsonify({"error": f"Camera with id {camera_id} does not exist"}), 404
    else:
        camera_id = len(cameras)
        cameras.append(Camera(ip=ip, port=port, username=username, password=password, url=url, id=camera_id))
        return jsonify({"message": "Camera added successfully", "camera_id": camera_id}), 200
        # redirect(url_for('/'))

@app.route('/update_camera_credentials', methods=['POST'])
def update_camera_credentials():
    data = request.json
    camera_id = data.get('camera_id')
    ip = data.get('ip')
    port = data.get('port')
    username = data.get('username')
    password = data.get('password')

    if camera_id in cameras:
        cameras[camera_id]['ip'] = ip
        cameras[camera_id]['port'] = port
        cameras[camera_id]['username'] = username
        cameras[camera_id]['password'] = password
        return jsonify({"message": "Camera credentials updated successfully"})
    else:
        return jsonify({"error": "Camera not found"}), 404

@app.route('/get_camera_info/<int:cameraId>', methods=['GET'])
def get_camera_info(cameraId:int):
    for camera in cameras:
        if camera.id == cameraId:
            camera_info = camera
            break
    if camera_info:
        return jsonify({'success': True, 'cameraInfo': camera_info.__dict__})
    else:
        return jsonify({'success': False, 'error': 'Camera not found'}), 404

if __name__ == "__main__":
    try:
        Thread(target=run_camera_command).start()
        # add default camera to list
        cameras.append(Camera(ip='localhost', port='8554', username='username', password='password', url='/stream', id=0))
        cameras.append(Camera(ip='192.168.1.195', port='8554', username='username', password='password', url='/stream', id=1))
        cameras.append(Camera(ip='192.168.1.195', port='8554', username='username', password='password', url='/stream', id=2))
        cameras.append(Camera(ip='192.168.1.195', port='8554', username='username', password='password', url='/stream', id=3))
        
        app.run("0.0.0.0", "5000", False)
    except KeyboardInterrupt:
        stop_camera_command()
        print("Exiting...")
