from flask import Flask, Response, render_template, request, jsonify, send_from_directory
from threading import Thread
import subprocess
import psutil
import cv2
import os
from datetime import datetime, timedelta
from flask_cors import CORS

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
RECORDINGS_FOLDER = 'recordings'
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)

app = Flask(__name__)

username = "username"
password = "password"
camera_process = None
status = False

continuous_record = False

def record_stream():
    global continuous_record
    print("Recording started...")
    record_duration = 15
    start_time = datetime.now()
    
    filename = f"{RECORDINGS_FOLDER}/record_{datetime.now().strftime('%H:%M:%S')}.avi"
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))

    cap = cv2.VideoCapture(f'rtsp://{username}:{password}@127.0.0.1:8554/stream', cv2.CAP_FFMPEG)
    
    while continuous_record:
        ret, frame = cap.read()
        if not ret:
            break

        out.write(frame)
        
        if datetime.now() - start_time >= timedelta(seconds=record_duration):
            print("Recording stopped...")
            # continuous_record = False
            break
    
    cap.release()
    out.release()

    if continuous_record:
        print("Recording duration exceeded. Restarting recording...")
        record_stream()

def start_continuous_record():
    global continuous_record
    if not continuous_record:
        continuous_record = True
        Thread(target=record_stream).start()
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

def gen_frames():
    cap = cv2.VideoCapture(f'rtsp://{username}:{password}@127.0.0.1:8554/stream', cv2.CAP_FFMPEG)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cv2.putText(frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                break
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed', methods=['GET'])
def video_feed():
    gen = gen_frames()
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
    return render_template('index.html', status=status, username=username, password=password, recordings=recordings)

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
            'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S") # type: ignore
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

if __name__ == "__main__":
    try:
        Thread(target=run_camera_command).start()
        app.run("0.0.0.0", "5000", True)
    except KeyboardInterrupt:
        stop_camera_command()
        print("Exiting...")
