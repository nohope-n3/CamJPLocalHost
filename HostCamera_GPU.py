import socket
import subprocess
import cv2
import time
import multiprocessing

# Function to get host IP
def get_host_IP():
    """Gets the local host IP address."""
    host_ip = socket.gethostbyname(socket.gethostname())
    print("Host IP address:", host_ip)
    return host_ip

# Function to convert IP to CIDR format
def convert_to_CIDR(host_ip):
    """Converts the host IP into a CIDR format."""
    octets = host_ip.split('.')
    network_address = '.'.join(octets[:3]) + '.0'
    network_range = f"{network_address}/24"
    return network_range

# Function to scan for devices in the network
def get_list_camera_IP(network_range):
    """Scans the network for IPs and filters those corresponding to Hikvision cameras."""
    # Use nmap to scan the network
    nmap_command = f"nmap -sn {network_range}"
    result = subprocess.run(nmap_command, shell=True, capture_output=True, text=True)

    print("\nScan results:")
    print(result.stdout)

    # Filter MAC address for Hikvision cameras
    filter_device = "80:BE:AF"  
    filtered_ips = []

    # Parse the nmap result to extract IPs
    lines = result.stdout.splitlines()
    for i in range(2, len(lines)):
        if filter_device in lines[i]:
            ip_address = lines[i-2].split()[-1]  
            filtered_ips.append(ip_address)

    if filtered_ips:
        print("Hikvision IPs found:")
        for ip in filtered_ips:
            print(ip)
    else:
        print("No Hikvision IP found.")
    
    return filtered_ips

# Video stream reset function
def reset_video_capture(cap, RTSP_ADDRESS):
    """Resets the video capture if a frame cannot be read."""
    print("Resetting video capture...")
    # Release the current capture object
    cap.release()  
     # Wait a bit before reinitializing
    time.sleep(1) 
     # Reinitialize the video capture
    cap = cv2.VideoCapture(RTSP_ADDRESS) 
    if not cap.isOpened():
        print("Failed to re-open video capture.")
    return cap.isOpened(), cap

# Create socket connection function
def create_socket(vps_ip, vps_port):
    """Creates a socket connection to the VPS."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((vps_ip, vps_port))
        return client_socket
    except socket.error as e:
        print(f"Error creating socket: {e}")
        return None

# Send frame to server function
def send_frame(client_socket, frame):
    """Sends a single video frame to the server over the socket."""
    try:
        # Encode the frame as JPEG
        _, jpeg = cv2.imencode('.jpg', frame)  
        # Convert frame to bytes
        frame_bytes = jpeg.tobytes()  

        # Check if the socket is open and send the frame
        if client_socket and client_socket.fileno() != -1:
            length = len(frame_bytes)
            # Send the length of the frame first
            client_socket.sendall(length.to_bytes(4, byteorder='big'))  
            # Send the actual frame
            client_socket.sendall(frame_bytes)  
        else:
            print("Socket is not open. Reconnecting...")
            return False
    except Exception as e:
        print(f"Error while sending frame: {e}")
        return False
    return True

# Function to handle video streaming for a single camera
def stream_single_camera(ip_address, vps_ip, vps_port):
    """Streams video from a single camera and sends it to the VPS."""
    ip_address = ip_address.strip("()")
    RTSP_ADDRESS = f"rtsp://admin:NohopeN3@{ip_address}:554/Streaming/Channels/102"

    # Initialize video capture for the camera
    cap = cv2.VideoCapture(RTSP_ADDRESS)

    if not cap.isOpened():
        print(f"Failed to connect to the camera at {ip_address}.")
        return

    # Initialize GPU-based frame processing if available
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        print("CUDA-enabled device found. Using GPU for frame processing.")
    else:
        print("CUDA-enabled device not found. Using CPU.")

    while True:
        client_socket = create_socket(vps_ip, vps_port)
        if not client_socket:
            print(f"Connection failed for camera at {ip_address}, retrying in 5 seconds...")
            time.sleep(5)
            continue

        print(f"Connected to server, starting video stream for camera at {ip_address}.")
        
        try:
            while True:
                ret, frame = cap.read()

                if not ret:
                    print(f"Error reading frame from camera at {ip_address}, resetting video capture.")
                    success, cap = reset_video_capture(cap, RTSP_ADDRESS)
                    # Exit if unable to reinitialize the video stream
                    if not success:
                        break  
                    continue

                # If GPU is available, upload the frame to GPU for processing
                if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)

                    # Process the frame on the GPU (example: resize)
                    gpu_frame = cv2.cuda.resize(gpu_frame, (640, 480))

                    # Download processed frame from GPU to CPU memory
                    frame = gpu_frame.download()

                # Send the frame to the server
                if not send_frame(client_socket, frame):
                    print(f"Socket lost for camera at {ip_address}, attempting to reconnect...")
                    break

        except Exception as e:
            print(f"Error during video streaming for camera at {ip_address}: {e}")
        finally:
            if client_socket:
                client_socket.close()

    # Release resources after completion
    if cap.isOpened():
        cap.release()
    cv2.destroyAllWindows()
    print(f"Video streaming ended for camera at {ip_address}.")

# Function to handle video streaming for multiple cameras (using multiprocessing)
def stream_multiple_cameras(ip_list, vps_ip, vps_port):
    """Streams video from multiple cameras concurrently."""
    processes = []
    for ip_address in ip_list:
        ip_address = ip_address.strip("()")
        process = multiprocessing.Process(target=stream_single_camera, args=(ip_address, vps_ip, vps_port))
        processes.append(process)
        process.start()

    # Wait for all processes to finish
    for process in processes:
        process.join()

    print("All video streams have ended.")


def main():
    # VPS's IP and port
    vps_ip = '160.22.122.122'
    vps_port = 8000

    # Get host IP and determine the network range
    host_ip = get_host_IP()
    network_range = convert_to_CIDR(host_ip=host_ip)

    # Get the list of camera IPs
    list_ip_address = get_list_camera_IP(network_range)

    #Start stream camera
    stream_single_camera(list_ip_address[0], vps_ip, vps_port)


if __name__ == "__main__":
    main()
