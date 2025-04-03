import multiprocessing
import logging
import time
import sys
from Config.load_config import load_configuration
from Core.stream_image import stream_multiple_cameras
from Core.scan_cam import get_host_IP, convert_to_CIDR, get_list_camera_IP


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    logging.info("Starting main process...")
    config = load_configuration()
    if config is None:
        logging.critical("Failed to load configuration. Exiting.")
        sys.exit(1)

    vps_ip = config['vps_ip']
    video_port = config['video_port']
    control_port = config['control_port']
    cam_user = config['cam_user']
    cam_password = config['cam_password']
    resize_frame = config['resize_frame']
    filter_devices = config["filter_devices"]

    try:
        host_ip = get_host_IP()
        if not host_ip:
            logging.error("Could not determine host IP address.")
            sys.exit(1)
        network_range = convert_to_CIDR(host_ip)
        if not network_range:
            logging.error("Could not determine network range (CIDR).")
            sys.exit(1)
        logging.info(f"Host IP: {host_ip}, Network Range: {network_range}")
    except Exception as e:
        logging.error(f"Error getting network information: {e}")
        sys.exit(1)

    logging.info(
        f"Scanning network {network_range} for devices: {filter_devices}")
    try:
        list_ip_address = get_list_camera_IP(network_range, filter_devices)
        logging.info(f"Found cameras: {list_ip_address}")
    except Exception as e:
        logging.error(f"Error scanning for cameras: {e}")
        list_ip_address = []
    if list_ip_address:
        logging.info(
            f"Starting streaming process for {len(list_ip_address)} cameras...")
        stream_process = multiprocessing.Process(
            target=stream_multiple_cameras,
            args=(list_ip_address, video_port, control_port,
                  vps_ip, cam_user, cam_password, resize_frame)
        )
        stream_process.daemon = True
        stream_process.start()

        try:
            while True:
                time.sleep(10)
                if not stream_process.is_alive():
                    logging.error(
                        "Streaming process has terminated unexpectedly. Exiting main process.")
                    break

        except KeyboardInterrupt:
            logging.info(
                "Keyboard interrupt received. Shutting down gracefully...")
            stream_process.terminate()
            stream_process.join(timeout=5)
            if stream_process.is_alive():
                logging.warning(
                    "Streaming process did not terminate gracefully. Sending SIGKILL.")
                stream_process.kill()
                stream_process.join()
            logging.info("Streaming process stopped.")

    else:
        logging.warning("No cameras found matching the criteria. Exiting.")


if __name__ == "__main__":
    main()
    logging.info("Main process finished.")
