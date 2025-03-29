import socket
import logging
import cv2
import requests
from requests.auth import HTTPDigestAuth

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def handle_control_commands(control_socket, cap, cam_user, cam_password, camera_ip):
    """Handles control commands received via the socket."""
    try:
        while True:
            command = control_socket.recv(1024).decode().strip()
            if not command:
                continue
            logging.info(f"Received control command: {command}")

            if command.startswith("RESOLUTION"):
                try:
                    _, width, height = command.split()
                    width, height = int(width), int(height)
                    logging.info(f"Changing resolution to {width}x{height}")
                    set_hikvision_resolution(
                        camera_ip, cam_user, cam_password, width, height)
                except ValueError:
                    logging.error(
                        "Invalid RESOLUTION command format.  Expected 'RESOLUTION <width> <height>'")

            elif command.startswith("MOVE"):
                logging.info(f"Camera movement command received: {command}")
                # Implement PTZ control logic here - Example placeholder:
                # move_camera(camera_ip, cam_user, cam_password, command)
                pass

            else:
                logging.warning(f"Unknown command received: {command}")

    except ConnectionResetError:
        logging.warning("Client disconnected.")
    except Exception as e:
        logging.error(f"Error handling control command: {e}")
    finally:
        logging.info("Closing control connection.")
        try:
            control_socket.close()
        except OSError as e:
            logging.error(f"Error closing control socket: {e}")


def set_hikvision_resolution(camera_ip, username, password, width, height):
    """Sets the Hikvision camera resolution using the ISAPI."""
    url = f"http://{camera_ip}/ISAPI/Streaming/channels/101/pictureSize"
    headers = {"Content-Type": "application/xml"}
    xml_data = f"""
    <PictureSize version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
        <videoResolutionWidth>{width}</videoResolutionWidth>
        <videoResolutionHeight>{height}</videoResolutionHeight>
    </PictureSize>
    """

    try:
        response = requests.put(url, data=xml_data.encode(
            'utf-8'), headers=headers, auth=HTTPDigestAuth(username, password), timeout=10)

        if response.status_code == 200:
            logging.info(f"Resolution set to {width}x{height} successfully!")
        else:
            logging.error(
                f"Failed to set resolution. Status Code: {response.status_code}, Response: {response.text}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")


# Add cam_user, cam_password, camera_ip
def listen_for_commands(port, cam_user, cam_password, camera_ip):
    """Listens for incoming control commands on the specified port."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('0.0.0.0', port) 
    try:
        server_socket.bind(server_address)
        server_socket.listen(1) 
        logging.info(f"Listening for control commands on port {port}...")

        while True:
            control_socket, client_address = server_socket.accept()
            logging.info(f"Accepted control connection from {client_address}")
            # Pass camera credentials and IP to the handler
            handle_control_commands(
                control_socket, None, cam_user, cam_password, camera_ip)

    except OSError as e:
        logging.error(f"Socket error: {e}")
    except KeyboardInterrupt:
        logging.info("Shutting down command listener.")
    finally:
        server_socket.close()


# Example usage (moved out of the main function):
if __name__ == '__main__':
    # Replace with actual values for testing
    camera_ip = "192.168.1.100"
    cam_user = "admin"
    cam_password = "password"
    control_port = 8034
    listen_for_commands(control_port, cam_user, cam_password, camera_ip)
