import multiprocessing
import stream_image
import receive_command
import scan_cam
import logging
import time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    logging.info("Starting main process...")

    vps_ip = '160.22.122.122'
    video_port = 8000
    control_port = 8034
    cam_user = "admin"
    cam_password = "CamProject12"
    resize_frame = (720, 480)

    host_ip = scan_cam.get_host_IP()
    network_range = scan_cam.convert_to_CIDR(host_ip)

    # List camera name
    filter_devices = ["Hikvision"]  # Add to scan more device
    list_ip_address = scan_cam.get_list_camera_IP(
        network_range, filter_devices)

    if list_ip_address:
        stream_process = multiprocessing.Process(
            target=stream_image.stream_multiple_cameras,
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
                        "Streaming process has terminated unexpectedly. Exiting.")
                    break

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received.  Shutting down...")
            stream_process.terminate()
            stream_process.join(timeout=5)

    else:
        logging.warning("No camera found.")


if __name__ == "__main__":
    main()
