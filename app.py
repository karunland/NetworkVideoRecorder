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

continuous_record = False

def record_stream(user: str = None, passw: str = None, ip: str = None, port: str = None, url: str = None):
    global continuous_record

    while continuous_record:
        print("Recording started...")
        record_duration = 15
        
        filename = f"{RECORDINGS_FOLDER}/record_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]}.avi"
        
        # Construct the ffmpeg command
        command = ['ffmpeg', '-i', f'rtsp://{ user + ":" + passw + "@" if user and passw else ""}{ip}{":"+ port if port else ""}{url if url else ""}',
                   '-t', str(record_duration), '-c:v', 'copy', filename]
        
        # Start the recording process
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for the recording to finish
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"Error occurred during recording: {stderr.decode('utf-8')}")
        else:
            print("Recording finished.")

        
        if continuous_record:
            print("Recording duration exceeded. Restarting recording...")
            record_stream(user, passw, ip, port, url)
        else:
            print("Recording stopped.")
            break


def start_continuous_record():
    global continuous_record
    if not continuous_record:
        continuous_record = True
        Thread(target=record_stream(**{'ip': '192.168.100.101'})).start()
        return {"message": "Continuous recording started successfully"}
    else:
        return {"message": "Continuous recording is already running"}


def stop_continuous_record():
    global continuous_record
    if continuous_record:
        continuous_record = False
        return {"message": "Continuous recording stopped successfully"}
    else:
        return {"message": "Continuous recording is not running"}


@app.route('/start_continuous_record', methods=['GET'])
def start_continuous_record_route():
    return jsonify(start_continuous_record())


@app.route('/stop_continuous_record', methods=['GET'])
def stop_continuous_record_route():
    return jsonify(stop_continuous_record())

def gen_frames(camera: Camera):
    # app = f'rtsp://{ user + "@" + passw if user and passw is not None else ""}{ip}{":"+ port if port else ""}{port if port else ""}{url if url else ""}'
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

    # camera.start_live_feed()

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
@app.route('/home', methods=['GET', 'POST', 'PUT'])
def index():
    global username, password, status
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
    return render_template('index.html', status=status, username=username, password=password, recordings=recordings, cameras=cameras)

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
        'data': recordings
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
def add_camera():
    global cameras
    data = request.json
    ip = data.get('ip')
    port = data.get('port')
    username = data.get('username')
    password = data.get('password')

    camera_id = len(cameras) + 1
    cameras[camera_id] = Camera(ip, port, username, password)
    # return jsonify({"message": "Camera added successfully", "camera_id": camera_id})
    return redirect(url_for('/'))

# # Program yeniden başladığında kameraları sil
# @app._got_first_request
# def clear_cameras():
#     global cameras
#     cameras = {}

if __name__ == "__main__":
    try:
        # Thread(target=run_camera_command).start()
        # add default camera to list
        cameras.append(Camera(ip='localhost', port='8554', username='admin', password='admin', url='/stream'))
        app.run("0.0.0.0", "5000", True)
    except KeyboardInterrupt:
        stop_camera_command()
        print("Exiting...")
