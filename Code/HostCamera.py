import socket
import subprocess
import cv2
import time
import multiprocessing
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to get host IP
def get_host_IP():
    """Gets the local host IP address."""
    host_ip = socket.gethostbyname(socket.gethostname())
    logging.info(f"Host IP address: {host_ip}")
    return host_ip

# Function to convert IP to CIDR format
def convert_to_CIDR(host_ip):
    """Converts the host IP into a CIDR format."""
    octets = host_ip.split('.')
    network_address = '.'.join(octets[:3]) + '.0'
    network_range = f"{network_address}/24"
    logging.info(f"Network range: {network_range}")
    return network_range

# Function to scan for devices in the network
def get_list_camera_IP(network_range):
    """Scans the network for IPs and filters those corresponding to Hikvision cameras."""
    # Use nmap to scan the network
    nmap_command = f"nmap -sn {network_range}"
    try:
        result = subprocess.run(nmap_command, shell=True, capture_output=True, text=True, check=True)
        logging.info(f"\nScan results:\n{result.stdout}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running nmap: {e}")
        return []

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
        logging.info("Hikvision IPs found:")
        for ip in filtered_ips:
            logging.info(ip)
    else:
        logging.warning("No Hikvision IP found.")
    
    return filtered_ips

# Video stream reset function
def reset_video_capture(cap, RTSP_ADDRESS):
    """Resets the video capture if a frame cannot be read."""
    logging.info("Resetting video capture...")
    # Release the current capture object
    cap.release()
    # Wait a bit before reinitializing
    time.sleep(1) 
    # Reinitialize the video capture
    cap = cv2.VideoCapture(RTSP_ADDRESS)
    if not cap.isOpened():
        logging.error("Failed to re-open video capture.")
    return cap.isOpened(), cap

# Create socket connection function
def create_socket(vps_ip, vps_port):
    """Creates a socket connection to the VPS."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((vps_ip, vps_port))
        logging.info(f"Socket created successfully to: {vps_ip}:{vps_port}")
        return client_socket
    except socket.error as e:
        logging.error(f"Error creating socket: {e}")
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
            logging.error("Socket is not open. Reconnecting...")
            return False
    except Exception as e:
        logging.error(f"Error while sending frame: {e}")
        return False
    return True

# Function to handle video streaming for a single camera
def stream_single_camera(ip_address, vps_ip, vps_port, cam_user, cam_password, resize_frame=(0,0)):
    """Streams video from a single camera and sends it to the VPS."""
    ip_address = ip_address.strip("()")
    RTSP_ADDRESS = f"rtsp://{cam_user}:{cam_password}@{ip_address}:554/Streaming/Channels/102"

    # Initialize video capture for the camera
    cap = cv2.VideoCapture(RTSP_ADDRESS)
    if not cap.isOpened():
        logging.error(f"Failed to connect to the camera at {ip_address}.")
        return

    client_socket = None
    try:
        # Create socket connection once here
        client_socket = create_socket(vps_ip, vps_port)
        if not client_socket:
             logging.error(f"Connection failed for camera at {ip_address}, skipping stream.")
             return
        logging.info(f"Connected to server, starting video stream for camera at {ip_address}.")
        
        while True:
            ret, frame = cap.read()

            if not ret:
                logging.warning(f"Error reading frame from camera at {ip_address}, resetting video capture.")
                success, cap = reset_video_capture(cap, RTSP_ADDRESS)
                if not success:
                    logging.error(f"Failed to reinitialize video stream for camera at {ip_address}")
                    break
                continue

            if all(resize_frame):
                frame = cv2.resize(frame, resize_frame)

            # Send the frame to the server
            if not send_frame(client_socket, frame):
                logging.warning(f"Socket lost for camera at {ip_address}, attempting to reconnect...")
                # Attempt to reconnect
                if client_socket:
                    client_socket.close()
                client_socket = create_socket(vps_ip, vps_port)
                if not client_socket:
                    logging.error(f"Reconnection failed for camera at {ip_address}, skipping stream.")
                    break
        
    except Exception as e:
            logging.error(f"Error during video streaming for camera at {ip_address}: {e}")
    finally:
        # Release resources
        if cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        if client_socket:
            client_socket.close()
        logging.info(f"Video streaming ended for camera at {ip_address}.")

# Function to handle video streaming for multiple cameras (using multiprocessing)
def stream_multiple_cameras(ip_list, vps_ip, vps_port, cam_user, cam_password, resize_frame = (0,0)):
    """Streams video from multiple cameras concurrently."""
    processes = []
    try:
        for ip_address in ip_list:
            process = multiprocessing.Process(target=stream_single_camera, args=(ip_address, vps_ip, vps_port, cam_user, cam_password, resize_frame))
            processes.append(process)
            process.start()

        # Wait for all processes to finish
        for process in processes:
            process.join()
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        logging.info("All video streams have ended.")
        
def main():
    # VPS's IP and port
    vps_ip = '160.22.122.122'
    vps_port = 8000
    # User and Password
    cam_user = 'admin'
    cam_password = 'CamProject12'
    #Optional resizing parameters
    resize_frame = (720, 480)

    # Get host IP and determine the network range
    host_ip = get_host_IP()
    network_range = convert_to_CIDR(host_ip=host_ip)

    # Get the list of camera IPs
    list_ip_address = get_list_camera_IP(network_range)

    if list_ip_address:
        #Start stream camera
        stream_multiple_cameras(list_ip_address, vps_ip, vps_port, cam_user, cam_password, resize_frame)
    else:
        logging.warning("No camera found.")

if __name__ == "__main__":
    main()