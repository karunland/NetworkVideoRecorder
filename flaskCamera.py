from flask import Flask, Response, request
import cv2
import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
app = Flask(__name__)

@app.after_request
def add_header(r):
	r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	r.headers["Pragma"] = "no-cache"
	r.headers["Expires"] = "0"
	r.headers["Cache-Control"] = "public, max-age=0"
	return r

def gen_frames(username='username', password='password'):
    cap = cv2.VideoCapture(f'rtsp://{username}:{password}@127.0.0.1:8554/stream', cv2.CAP_FFMPEG)    
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                break
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n') 

@app.route('/video_feed', methods=['GET'])
def video_feed():
    # username = request.args.get('username')
    # password = request.args.get('password')

    # print(username, password)
    gen = gen_frames()
    return Response(gen, mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
