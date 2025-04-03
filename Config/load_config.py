import os
import logging
import configparser
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def load_configuration():
    """Loads configuration from .env and cam.cfg files."""
    config_data = {}

    env_file = 'Config/.env'
    config_file = 'Config/cam.cfg'

    # Load Credentials
    if not os.path.exists(env_file):
        logging.warning(
            f"Environment file '{env_file}' not found. Trying environment variables.")
    load_dotenv()
    config_data['cam_user'] = os.getenv("CAM_USER")
    config_data['cam_password'] = os.getenv("CAM_PASSWORD")

    if not config_data['cam_user'] or not config_data['cam_password']:
        logging.error(
            f"CAM_USER or CAM_PASSWORD not found in '{env_file}' or environment variables.")
        return None

    # Load camera config
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        logging.error(f"Configuration file '{config_file}' not found.")
        return None

    try:
        config.read(config_file)

        # Load Network settings
        config_data['vps_ip'] = config.get('Network', 'vps_ip')
        config_data['video_port'] = config.getint('Network', 'video_port')
        config_data['control_port'] = config.getint('Network', 'control_port')

        # Load Video settings
        resize_width = config.getint('Video', 'resize_width')
        resize_height = config.getint('Video', 'resize_height')
        config_data['resize_frame'] = (resize_width, resize_height)

        # Load Scanning settings
        filter_devices_raw = config.get(
            'Scanning', 'filter_devices', fallback='')
        filter_devices_block_cleaned = filter_devices_raw.strip()

        if filter_devices_block_cleaned:
            config_data['filter_devices'] = [
                item.strip()
                for item in filter_devices_block_cleaned.split(',')
                if item.strip()
            ]

        else:
            logging.warning(
                f"'filter_devices' not found or empty in [{config_file} -> Scanning]. Scanning might include unwanted devices.")
            config_data['filter_devices'] = ['Hikvision']

    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logging.error(f"Error reading configuration from '{config_file}': {e}")
        return None
    except Exception as e:
        logging.error(
            f"An unexpected error occurred reading '{config_file}': {e}")
        return None

    logging.info("Configuration loaded successfully.")
    logging.debug(f"VPS IP: {config_data['vps_ip']}")
    logging.debug(f"Video Port: {config_data['video_port']}")
    logging.debug(f"Control Port: {config_data['control_port']}")
    logging.debug(f"Resize Frame: {config_data['resize_frame']}")
    logging.debug(f"Cam User: {config_data['cam_user']}")

    return config_data
