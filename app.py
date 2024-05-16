import threading
import time
from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    jsonify,
    send_from_directory,
    url_for,
)
from threading import Thread
import subprocess
import psutil
import cv2
import os
from datetime import datetime, timedelta

# from flask_cors import CORS
from cam import Camera

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
RECORDINGS_FOLDER = "recordings"
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)

app = Flask(__name__)

username = "username"
password = "password"
cameras = []


def reduce_resolution(frame, scale_percent=50):
    original_height, original_width = frame.shape[:2]

    width = int(original_width * scale_percent / 100)
    height = int(original_height * scale_percent / 100)
    dim = (width, height)

    low_res_frame = cv2.resize(frame, dim, interpolation=cv2.INTER_LINEAR)

    resized_frame = cv2.resize(
        low_res_frame,
        (original_width, original_height),
        interpolation=cv2.INTER_NEAREST,
    )

    return resized_frame


def updateCamera(camera: Camera):
    global cameras
    for item in cameras:
        if item.id == camera.id:
            item = camera
            break


def record_stream(camera: Camera):
    while True:
        if camera.recordingStatus is False:
            print(f"Recording stopped for camera {camera.id}.")
            break

        print(f"Recording started for camera {camera.id}...")
        record_duration = 15

        filename = f"{RECORDINGS_FOLDER}/record_{camera.id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]}.avi"

        command = [
            "ffmpeg",
            "-i",
            camera.__str__(),
            "-t",
            str(record_duration),
            "-c:v",
            "copy",
            filename,
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Error occurred during recording for camera {camera.id}: {stderr.decode('utf-8')}")

        print(f"Recording duration exceeded for camera {camera.id}. Restarting recording...")


@app.route("/start_continuous_record/<int:camera_id>", methods=["GET"])
def start_continuous_record_route(camera_id):
    for camera in cameras:
        if camera.id == camera_id:
            camera = camera
            break
    if camera is None:
        return jsonify({"error": "Camera not found", "isSuccess": False})

    if camera.streamStatus == False:
        return jsonify({"message": f"Camera {camera_id} is not streaming. Start streaming first.", "isSuccess": False})

    camera.recordingStatus = True
    updateCamera(camera)
    Thread(target=record_stream, kwargs={"camera": camera}).start()
    return jsonify({"message": f"Continuous recording started successfully for camera {camera.id}", "isSuccess": True})


@app.route("/stop_continuous_record/<int:camera_id>", methods=["GET"])
def stop_continuous_record_route(camera_id):
    for camera in cameras:
        if camera.id == camera_id:
            camera = camera
            break
    if camera:
        if camera.recordingStatus is False:
            return jsonify({"message": f"No active recording process found for camera {camera_id}", "isSuccess": False})

        camera.recordingStatus = False
        updateCamera(camera)
        return jsonify({"message": f"Continuous recording stopped successfully for camera {camera_id}", "isSuccess": True})
    else:
        return jsonify({"error": "Camera not found", "isSuccess": False})


def gen_frames(id:int):
    global cameras
    camera = None
    for item in cameras:
        if item.id == id:
            camera = item
            break
    if camera is None:
        return jsonify({"isSuccess": False, "message": "Camera not found"})

    url = camera.__str__()
    print(url)
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    quality = int(camera.quality)
    if not cap.isOpened():
        camera.streamStatus = False
        camera.getStream = False
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + b"Error: Could not open camera stream\r\n"
        )
        return

    while True:
       
        success, frame = cap.read()
        if not success:
            camera.streamStatus = False
            camera.getStream = False
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + b"Error: Could not read frame from camera stream\r\n"
            )
            break

        frame = reduce_resolution(frame, quality)

        current_time = datetime.now().strftime("%H:%M:%S:%f")
        cv2.putText(
            frame, current_time, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
        )

        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            camera.streamStatus = False
            camera.getStream = False
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + b"Error: Could not encode frame to JPEG\r\n"
            )
            break

        frame = buffer.tobytes()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


@app.route("/video_feed", methods=["GET"])
def video_feed():
    id = request.args.get("id")
    gen = gen_frames(int(id))
    return Response(gen, mimetype="multipart/x-mixed-replace; boundary=frame")


def run_camera_command(camera: Camera):

    camera.cmd = f"rpicam-vid -n -p 0,0,1280,720 --vflip --hflip --framerate 30 --bitrate 1000000 -t 0 --inline -o - | cvlc -vvv stream:///dev/stdin --sout '#rtp{{sdp=rtsp://:8554/stream}}' :demux=h264 :h264-fps=30 --sout-rtsp-user {username} --sout-rtsp-pwd {password}"

    camera.camera_process = subprocess.Popen(
        camera.cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    camera.streamStatus = True


def stop_camera_command():
    global cameras
    if cameras.camera_process:
        parent_pid = cameras.camera_process.pid
        parent = psutil.Process(parent_pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
        cameras.camera_process.wait()
        cameras.camera_process = None
        cameras.streamStatus = False


@app.route("/", methods=["GET", "POST", "PUT"])
def index():
    return render_template("index.html", cameras=cameras, camera_count=len(cameras))


@app.route("/recordings", methods=["GET", "POST"])
def recording_list():
    recordings = []
    for filename in os.listdir(RECORDINGS_FOLDER):
        filepath = os.path.join(RECORDINGS_FOLDER, filename)
        file_stat = os.stat(filepath)
        file_info = {
            "name": filename,
            "size": f"{file_stat.st_size / (1024 * 1024):.2} MB",
            "created_at": datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),  # type: ignore
        }
        recordings.append(file_info)

    recordings = sorted(recordings, key=lambda x: x["created_at"], reverse=True)

    return render_template("recordings.html", recordings=recordings)


@app.route("/stop", methods=["GET"])
def stop_camera():
    stop_camera_command()
    return jsonify({"message": "Camera stopped successfully", "isSuccess": True})


@app.route("/recordings/<path:filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(RECORDINGS_FOLDER, filename, as_attachment=True)


@app.route("/add_camera", methods=["POST"])
def add_or_update_camera():
    global cameras
    data = request.json
    ip = data.get("ip")

    if ip == "" or ip is None:
        return jsonify({"isSuccess": False, "message": "bad request"})

    camera_id = data.get("id")
    username = data.get("username")
    password = data.get("password")
    url = data.get("url")
    port = data.get("port")
    quality = data.get("quality")

    if camera_id is not None and camera_id != "":
        camera_id = int(camera_id)
        if camera_id >= 0 and camera_id < len(cameras):
            cameras[camera_id].ip = ip
            cameras[camera_id].port = port
            cameras[camera_id].username = username
            cameras[camera_id].password = password
            cameras[camera_id].url = url
            cameras[camera_id].quality = quality
            return jsonify(
                {
                    "isSuccess": True,
                    "message": f"Camera updated successfully with id {camera_id}",
                }
            )
        else:
            return jsonify(
                {
                    "isSuccess": False,
                    "message": f"Camera with id {camera_id} does not exist",
                }
            )
    else:
        camera_id = len(cameras)
        cameras.append(
            Camera(
                ip=ip,
                port=port,
                username=username,
                password=password,
                url=url,
                id=camera_id,
                quality=quality,
            )
        )
        return jsonify({"message": "Camera added successfully", "camera_id": camera_id, "isSuccess": True})


@app.route("/update_camera_credentials", methods=["POST"])
def update_camera_credentials():
    global cameras
    data = request.json
    camera_id = data.get("camera_id")
    ip = data.get("ip")
    port = data.get("port")
    username = data.get("username")
    password = data.get("password")

    if camera_id in cameras:
        cameras[camera_id]["ip"] = ip
        cameras[camera_id]["port"] = port
        cameras[camera_id]["username"] = username
        cameras[camera_id]["password"] = password
        return jsonify({"message": "Camera credentials updated successfully", "isSuccess": True})
    else:
        return jsonify({"error": "Camera not found", "isSuccess": False})


@app.route("/get_camera_info/<int:cameraId>", methods=["GET"])
def get_camera_info(cameraId: int):
    for camera in cameras:
        if camera.id == cameraId:
            camera_info = camera
            break
    if camera_info:
        return jsonify({"isSuccess": True, "cameraInfo": camera_info.__dict__})
    else:
        return jsonify({"isSuccess": False, "error": "Camera not found"})


@app.route("/delete_camera/<int:camera_id>", methods=["DELETE"])
def delete_camera(camera_id):
    global cameras
    if 0 <= camera_id < len(cameras):
        del cameras[camera_id]
        return jsonify(
            {
                "isSuccess": True,
                "message": f"Camera with ID {camera_id} deleted successfully",
            }
        )
    else:
        return jsonify(
            {
                "isSuccess": False,
                "message": f"Camera with ID {camera_id} does not exist",
            }
        )


@app.route("/stopStream/<int:camera_id>", methods=["GET"])
def stop_stream(camera_id):
    global cameras
    mcamera = None
    for camera in cameras:
        if camera.id == camera_id:
            mcamera = camera
    if mcamera is None:
        return jsonify({"message": f"Camera {camera_id} not found", "isSuccess": False})
    cameras[camera_id].getStream = False
    return jsonify(
        {"message": f"Stream stopped for camera {camera_id}", "isSuccess": True}
    )


@app.route("/startStream/<int:camera_id>", methods=["GET"])
def start_stream(camera_id):
    global cameras
    mcamera = None
    for camera in cameras:
        if camera.id == camera_id:
            mcamera = camera
    if mcamera is None:
        return jsonify({"message": f"Camera {camera_id} not found", "isSuccess": False})
    cameras[camera_id].getStream = True
    return jsonify(
        {"message": f"Stream started for camera {camera_id}", "isSuccess": True}
    )


@app.route("/cameras", methods=["GET"])
def get_cameras():
    camera_data = []
    for camera in cameras:
        camera_dict = camera.__dict__.copy()
        if 'camera_process' in camera_dict:
            del camera_dict['camera_process']
        camera_data.append(camera_dict)

    return jsonify(camera_data)


def check_camera_status(camera: Camera):
    try:
        subprocess.run(['ffmpeg', '-rtsp_transport', camera.rtsp_transport, '-i', camera.__str__(), '-vframes', '1', '-f', 'null', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def update_camera_statuses():
    global cameras
    time.sleep(2)
    while True:
        print("Kamera durumları güncelleniyor...")
        for camera in cameras:
            camera.streamStatus = check_camera_status(camera)
            print(f"Kamera {camera.id} - Canlı Yayın Durumu: {'Açık' if camera.streamStatus else 'Kapalı'}")

if __name__ == "__main__":
    try:
        myCam = Camera(
                ip="127.0.0.1",
                port="8554",
                username=f"{username}",
                password=f"{password}",
                url="/stream",
                id=0,
                getStream=False,
                rtsp_transport='udp' # rpi3 kamera icin rtsp transport ayari
            )
        
        update_thread = Thread(target=update_camera_statuses)
        rpi_cam_command = Thread(target=run_camera_command, args=(myCam,))
        rpi_cam_command.daemon = True
        update_thread.daemon = True
        update_thread.start()
        rpi_cam_command.start()
        time.sleep(1)
        
        cameras.append(myCam)
        cameras.append(Camera(ip='192.168.100.102', port='', username=f"", password=f"", url='', id=1, quality=50, getStream=True))
        cameras.append(Camera(ip='192.168.100.103', port='', username=f"", password=f"", url='', id=2, quality=50, getStream=False))
        # cameras.append(Camera(ip='10.42.0.141', port='8554', username=f"{username}", password=f"{password}", url='/stream', id=1))

        app.run("0.0.0.0", "5000", False)
    except KeyboardInterrupt:
        stop_camera_command()
        print("Exiting...")
