
class Camera:
    def __init__(self, ip: str = "", port: str = "", username: str = "", password: str = "", url: str = "", multiCastUrl:str = "", id:int = 0, getStream:bool = False, recordingStatus:bool = False, streamStatus:bool = True, quality:int = 50, rtsp_transport:str = 'udp'):
        self.id = id
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.url = url
        self.multiCastUrl = multiCastUrl
        # kamera kayit durumu
        self.recordingStatus = recordingStatus
        # suan stream geliyormu
        self.streamStatus = streamStatus
        # arayuze stream gonderilsinmi
        self.getStream = getStream
        # raspberry pi camera servisi verisi icin
        self.camera_process = None
        # arayuze gelen kamera kalitesi
        self.quality = quality
        self.rtsp_transport = rtsp_transport
    
    def __str__(self):
        return f"rtsp://{self.username + ':' + self.password + '@' if self.username and self.password else ''}{self.ip}{':' + self.port if self.port else ''}{self.url if self.url else ''}"

    def __repr__(self):
        return f"rtsp://{self.username + ':' + self.password + '@' if self.username and self.password else ''}{self.ip}{':' + self.port if self.port else ''}{self.url if self.url else ''}"

    def __eq__(self, other):
        return self.ip == other.ip and self.port == other.port and self.username == other.username and self.password == other.password and self.url == other.url

    def __hash__(self):
        return hash((self.ip, self.port, self.username, self.password, self.url))

    def __lt__(self, other):
        return self.ip < other.ip

    def __gt__(self, other):
        return self.ip > other.ip

    def __le__(self, other):
        return self.ip <= other.ip

    def __ge__(self, other):
        return self.ip >= other.ip

    def __ne__(self, other):
        return self.ip != other.ip

    def __contains__(self, item):
        return item in self.__dict__.values()

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __bool__(self):
        return bool(self.__dict__)

    def __getattr__(self, item):
        return self.__dict__.get(item)

    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def __delattr__(self, item):
        del self.__dict__[item]

    def __add__(self, other):
        return self.ip + other.ip
