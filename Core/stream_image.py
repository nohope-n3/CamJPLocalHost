import socket
import cv2
import numpy as np
from queue import Queue, Empty
from threading import Thread, Event
import time
import logging
import queue  #

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

SHOW_FRAME = False  # Set to True to display combined stream locally, False to disable display
WINDOW_NAME = "Combined Stream"  # Name of the OpenCV display window
# Adjust this to control the width allocated per camera in the display
WINDOW_WIDTH_PER_CAMERA = 720
WINDOW_HEIGHT = 480  # Adjust this to control the height of the display window



def create_socket(ip, port, retries=0, delay=5):
    """Attempt to create a socket connection with retries. If retries=0, loop indefinitely."""
    attempt = 0
    while True:
        attempt += 1
        logging.info(f"Attempting socket connection to {ip}:{port} (Attempt {attempt})...")
        client_socket = None  # Ensure socket is None at the start of each attempt
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10) # Maybe slightly shorter timeout for connect?
            client_socket.connect((ip, port))
            logging.info(f"Socket connected successfully to {ip}:{port}")
            return client_socket  # Return the connected socket

        except socket.error as e:
            logging.error(f"Socket connection attempt {attempt} failed: {e}")
            if client_socket:
                client_socket.close() # Close the failed socket object

            # Check retry condition
            # Using '!=' covers both infinite (0) and finite retries
            if retries != 0 and attempt >= retries:
                logging.error(f"Max retries ({retries}) reached. Failed to connect to {ip}:{port}.")
                break # Exit loop after max retries

            # If retries == 0 or attempt < retries, wait and retry
            logging.info(f"Retrying connection in {delay} seconds...")
            time.sleep(delay)
        # No finally block needed here for managing the socket object itself
    return None # Return None if all retries failed


def capture_camera(ip_address, cam_user, cam_password, resize_frame, frame_queue, stop_event):
    """Captures video frames from an RTSP camera and puts them into a queue.
       If frame capture fails, puts a blank (black) frame into the queue instead.
    """
    RTSP_ADDRESS = f"rtsp://{cam_user}:{cam_password}@{ip_address}:554/Streaming/Channels/102"
    cap = cv2.VideoCapture(RTSP_ADDRESS)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        logging.error(f"Failed to connect to camera at {ip_address}.")
        # Even if camera connection fails initially, we will still send blank frames
        # so that the merged stream is consistent in frame count.

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                logging.warning(
                    f"Error reading frame from {ip_address}, using blank frame.")
                # Create a blank (black) frame of the desired size
                # Height, Width, Channels
                blank_frame = np.zeros(
                    (resize_frame[1], resize_frame[0], 3), dtype=np.uint8)
                frame_to_queue = blank_frame  # Use blank frame

                # Optionally attempt reconnect (you can keep or remove this part)
                cap.release()
                time.sleep(0.1)
                cap = cv2.VideoCapture(RTSP_ADDRESS)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            else:  # Frame read successfully
                if resize_frame[0] > 0 and resize_frame[1] > 0:
                    frame_to_queue = cv2.resize(frame, resize_frame)
                else:
                    frame_to_queue = frame  # Use original frame if no resizing
            try:
                # Put either captured frame or blank frame
                frame_queue.put(frame_to_queue, timeout=0.01)
            except queue.Full:
                logging.warning(
                    f"Frame queue full for {ip_address}, dropping frame.")
                try:
                    frame_queue.get_nowait()  # Discard oldest frame
                except queue.Empty:
                    pass
                continue

    except Exception as e:
        logging.error(f"Capture error for {ip_address}: {e}")
    finally:
        cap.release()
        logging.info(f"Capture stopped for {ip_address}.")


def stream_merged_frames(queues, video_socket, vps_ip, video_port, stop_event, num_cameras, resize_frame=(0, 0), max_reconnect_attempts=5, reconnect_delay=5):
    """Merges frames, using last good frame if queue is empty, ensures consistent merged frame size,
       and streams the combined frame over TCP. Avoids black frames for temporary camera drops.
    """
    reconnect_attempts = 0

    # Create a named window with a fixed size for local display
    if SHOW_FRAME:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        window_width = WINDOW_WIDTH_PER_CAMERA * num_cameras
        cv2.resizeWindow(WINDOW_NAME, window_width, WINDOW_HEIGHT)

    single_frame_height = resize_frame[1] if resize_frame[1] > 0 else WINDOW_HEIGHT
    single_frame_width = resize_frame[0] if resize_frame[0] > 0 else WINDOW_WIDTH_PER_CAMERA

    # Initialize list to store last good frames for each camera
    last_good_frames = [None] * num_cameras

    while not stop_event.is_set():
        if video_socket is None:
            logging.error("Video socket is None, attempting to reconnect...")
            video_socket = create_socket(vps_ip, video_port)
            if video_socket is None:
                reconnect_attempts += 1
                if reconnect_attempts > max_reconnect_attempts:
                    logging.error(
                        "Max socket reconnect attempts reached. Exiting streaming.")
                    break
                time.sleep(reconnect_delay)
                continue
            reconnect_attempts = 0

        try:
            start_time = time.time()

            frames_to_merge = []
            all_queues_empty = True  # Flag to check if all queues are empty in this iteration

            for i, queue in enumerate(queues):
                try:
                    frame = queue.get_nowait()  # Try to get the newest frame without waiting
                    # Update last good frame for this camera
                    last_good_frames[i] = frame
                    frames_to_merge.append(frame)
                    all_queues_empty = False  # At least one queue had a frame
                except Empty:
                    if last_good_frames[i] is not None:
                        logging.debug(
                            f"Queue {i} is empty, using last good frame.")
                        # Use last good frame
                        frames_to_merge.append(last_good_frames[i])
                    else:
                        logging.debug(
                            f"Queue {i} is empty, no last good frame available, using blank frame.")
                        blank_frame = np.zeros(
                            (single_frame_height, single_frame_width, 3), dtype=np.uint8)
                        # Use blank frame if no last good frame yet
                        frames_to_merge.append(blank_frame)

            if all_queues_empty:  # If all queues were empty, no new frames received in this iteration
                # Wait a bit before retrying to reduce CPU usage if all streams are down
                time.sleep(0.001)
                continue  # Skip to the next iteration

            combined_frame = np.hstack(frames_to_merge)

            # Display the combined frame locally if SHOW_FRAME is True
            if SHOW_FRAME:
                cv2.imshow(WINDOW_NAME, combined_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()
                    stop_event.set()
                    break

            _, jpeg = cv2.imencode('.jpg', combined_frame, [int(
                cv2.IMWRITE_JPEG_QUALITY), 70])
            if not _:
                logging.error("Failed to encode frame to JPEG.")
                continue
            frame_bytes = jpeg.tobytes()

            length_bytes = len(frame_bytes).to_bytes(4, byteorder='big')
            try:
                video_socket.sendall(length_bytes)
                video_socket.sendall(frame_bytes)
            except (BrokenPipeError, ConnectionResetError, socket.error) as e:
                logging.error(f"Connection lost while sending data: {e}")
                if video_socket:
                    try:
                        video_socket.shutdown(socket.SHUT_RDWR)
                    except OSError as e:
                        logging.error(f"Error during socket shutdown: {e}")
                    finally:
                        video_socket.close()
                video_socket = None
                time.sleep(reconnect_delay)
                continue

            end_time = time.time()
            processing_time = end_time - start_time

        except socket.timeout:
            logging.error(
                "Socket timeout occurred, attempting to reconnect...")
            if video_socket:
                try:
                    video_socket.shutdown(socket.SHUT_RDWR)
                except OSError as e:
                    logging.error(f"Error during socket shutdown: {e}")
                finally:
                    video_socket.close()
            video_socket = None
            time.sleep(reconnect_delay)

        except socket.error as e:
            logging.error(f"Streaming error: {e}")
            if video_socket:
                try:
                    video_socket.shutdown(socket.SHUT_RDWR)
                except OSError as e:
                    logging.error(f"Error during socket shutdown: {e}")
                finally:
                    video_socket.close()
            video_socket = None
            time.sleep(reconnect_delay)

        except Exception as e:
            logging.error(f"Unexpected error in stream_merged_frames: {e}")

    if video_socket:
        try:
            video_socket.shutdown(socket.SHUT_RDWR)
        except OSError as e:
            logging.error(f"Error during socket shutdown: {e}")
        finally:
            video_socket.close()
    logging.info("Streaming thread stopped.")


def stream_multiple_cameras(ip_addresses, video_port, control_port, vps_ip, cam_user, cam_password, resize_frame=(0, 0)):
    """Starts capture threads for multiple cameras and a stream thread for merged frames."""
    logging.info(
        f"Starting video stream from multiple cameras: {ip_addresses}...")

    if not ip_addresses:
        logging.error("No cameras provided to stream.")
        return

    # Create socket for video streaming
    video_socket = create_socket(vps_ip, video_port)
    if video_socket is None:
        logging.error("Failed to establish video socket connection. Aborting.")
        return

    # Queues for frames from each camera
    frame_queues = [Queue(maxsize=3) for _ in ip_addresses]
    stop_event = Event()  # Event to signal threads to stop

    capture_threads = []
    for ip_address, queue in zip(ip_addresses, frame_queues):
        thread = Thread(target=capture_camera,
                        args=(ip_address, cam_user, cam_password, resize_frame, queue, stop_event))
        thread.daemon = True  # Allow main process to exit even if threads are running
        thread.start()
        capture_threads.append(thread)

    stream_thread = Thread(target=stream_merged_frames,
                           args=(frame_queues, video_socket, vps_ip, video_port, stop_event, len(ip_addresses)))
    stream_thread.daemon = True  # Allow main process to exit even if thread is running
    stream_thread.start()

    try:
        while True:
            # Keep main thread alive and responsive to keyboard interrupts
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Shutting down...")
        stop_event.set()  # Signal all threads to stop
    finally:
        logging.info("Cleaning up threads and sockets...")
        stop_event.set()  # Ensure stop_event is set again in finally block
        for thread in capture_threads:
            thread.join(timeout=2.0)  # Wait for capture threads to finish
        stream_thread.join(timeout=2.0)  # Wait for stream thread to finish
        if video_socket:
            try:
                # Properly shutdown socket
                video_socket.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                logging.error(f"Error during socket shutdown: {e}")
            finally:
                video_socket.close()  # Ensure socket is closed

        logging.info(f"Streaming ended for cameras {ip_addresses}.")
