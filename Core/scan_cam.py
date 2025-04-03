import socket
import subprocess
import logging
import shutil
import os


def get_host_IP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('10.254.254.254', 1))
        host_ip = s.getsockname()[0]
    except Exception:
        host_ip = '127.0.0.1'
    finally:
        s.close()

    print(f"Host IP: {host_ip}")
    return host_ip


def convert_to_CIDR(host_ip):
    octets = host_ip.split('.')
    network_address = '.'.join(octets[:3]) + '.0'
    cidr = f"{network_address}/24"
    print(f"Converted to CIDR: {cidr}")
    return cidr


def get_list_camera_IP(network_range, filter_devices, nmap_retries=3):
    """
    Scans the network for camera IPs using nmap, with retries.

    Args:
        network_range: The CIDR network range to scan.
        filter_devices: A list of device identifiers (e.g., MAC address prefixes) to filter for.
        nmap_retries:   Number of times to retry the nmap scan.

    Returns:
        A list of camera IPs, or an empty list if no cameras are found or nmap fails.
    """
    if not shutil.which("nmap"):
        logging.error("nmap is not installed or not in PATH.")
        return []

    nmap_command = f"nmap -sn {network_range}"
    if os.name == 'posix':
        nmap_command = "sudo " + nmap_command

    for attempt in range(nmap_retries):
        print(
            f"Scanning network: {network_range} (Attempt {attempt+1}/{nmap_retries})")

        try:
            result = subprocess.run(nmap_command, shell=True,
                                    capture_output=True, text=True, check=True)
            print(f"Scan results:\n{result.stdout}")

            filtered_ips = []
            lines = result.stdout.splitlines()

            for i in range(2, len(lines)):
                line = lines[i]
                if any(device in line for device in filter_devices):
                    ip_address = lines[i-2].split()[-1]
                    filtered_ips.append(ip_address)

            ip_addresses = [ip.strip('()') for ip in filtered_ips]

            print(f"Filtered IPs: {ip_addresses}")
            return ip_addresses

        except subprocess.CalledProcessError as e:
            logging.error(
                f"Error running nmap (attempt {attempt+1}/{nmap_retries}): {e}")
            if attempt < nmap_retries - 1:
                print("Retrying nmap scan...")
            else:
                logging.error(
                    "Max nmap retries reached.  Returning empty list.")
                return []

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return []

    return []


if __name__ == "__main__":
    host_ip = get_host_IP()
    network_range = convert_to_CIDR(host_ip)
    camera_ips = get_list_camera_IP(network_range)
    print(f"List of Camera IPs: {camera_ips}")
