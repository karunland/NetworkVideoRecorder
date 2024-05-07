
ffmpeg -rtsp_transport tcp -i rtsp://admin:inside2016@192.168.1.25:554 -c:v hevc -b:v 2.5M -g 12 -c:a ac3 -b:a 196k -f mpegts -headers "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="  udp://10.220.220.62:5000


ffplay "udp://Aladdin:open sesame@224.1.1.1:5000/"

ffmpeg -i "udp://224.1.1.1:5000" -c:v copy -c:a copy output.mp4


rpicam-vid -n -p 0,0,640,480 --framerate 24 -t 0 --inline -o - | cvlc stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/stream1}' :demux=h264

ffplay rtsp://localhost:8554/stream1 -vf "setpts=N/30" -fflags nobuffer -flags low_delay -framedrop

// farklisi
rpicam-vid -n -p 0,0,640,480 --framerate 24 -t 0 --inline -o - | cvlc stream:///dev/stdin --sout '#rtp{sdp=rtsp://127.0.0.1:8554/stream1}' :demux=h264

ffmpeg -i rtsp://127.0.0.1:8554/stream1 -c:v hevc -b:v 2.5M -g 12 -c:a ac3 -b:a 196k -f mpegts -headers "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="  udp://10.42.0.141:5000

ffplay "udp://Aladdin:open sesame@10.42.0.141:5000/"


--------------
cvlc rtsp://admin:inside2016@192.168.1.25:554 --sout '#rtp{sdp=rtsp://127.0.0.1:5546}' --sout-rtsp-user admin --sout-rtsp-pwd password

ffmpeg -rtsp_transport tcp -i "rtsp://admin:inside2016@192.168.1.25:554" -f h264 - | cvlc -vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/stream1}' :demux=h264 :sout-rtsp-user username :sout-rtsp-pwd password


en son denedigim ve calisan versiyon
ffmpeg -rtsp_transport tcp -i "rtsp://admin:inside2016@192.168.1.25:554" -f h264 - | cvlc -vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/stream1}' :demux=h264  --sout-rtsp-user username --sout-rtsp-pwd password

ffplay rtsp://username:password@127.0.0.1:8554/stream1

