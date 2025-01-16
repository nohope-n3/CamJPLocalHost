# Camera Monitoring
This project allows to stream video from multiple Hikvision cameras and send the video stream to a server using UDP sockets. 

## Requirements
- Python 3.x
- OpenCV
- Nmap
Optional:
- PyTorch (with CUDA support)
- A compatible GPU with CUDA support

## Installation
1. **Clone the repository**:
    ```bash
    git clone git@github.com:nohope-n3/CamJPLocalHost.git

2. Create and activate a virtual environment (optional but recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Linux/macOS
    venv\Scripts\activate     # On Windows

3. Install dependencies:
    ```bash
    pip3 install -r requirements.txt --index-url https://download.pytorch.org/whl/cu124

4. Install Nmap:
    - For Ubuntu/Debian:
        ```bash
        sudo apt update
        sudo apt install nmap
    - For Windows:

        Run nmap_setup.exe file


## Setup
Before running the code, ensure you have the following:
- VPS IP and port: The IP address and port of the server that will receive the video stream.
- Camera credentials: The username and password for the Hikvision camera(s) you're streaming from.
- Network range: The local network range (the script automatically detects this from your host machine).