#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <thread>
#include <chrono>
#include <opencv2/opencv.hpp>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h>
#include <cstring>
#include <cstdlib>

using namespace std;  

// Function to get host IP address
string get_host_IP() {
    char host[256];
    gethostname(host, sizeof(host));
    struct hostent* he = gethostbyname(host);
    struct in_addr** addr_list = (struct in_addr**)he->h_addr_list;
    return inet_ntoa(*addr_list[0]);
}

// Convert IP to CIDR format
string convert_to_CIDR(const string& host_ip) {
    string network_address = host_ip.substr(0, host_ip.rfind('.') + 1) + "0";
    return network_address + "/24";
}

// Function to run nmap command to get list of camera IPs (using system calls)
vector<string> get_list_camera_IP(const string& network_range) {
    vector<string> filtered_ips;
    string command = "nmap -sn " + network_range + " | grep 80:BE:AF -B 2 | grep 'Nmap scan report' | awk '{print $5}'";
    FILE* fp = popen(command.c_str(), "r");
    if (fp == nullptr) {
        cerr << "Error executing nmap command." << endl;
        return filtered_ips;
    }

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), fp) != nullptr) {
        filtered_ips.push_back(buffer);
    }
    fclose(fp);

    return filtered_ips;
}

// Function to create socket connection
int create_socket(const string& vps_ip, int vps_port) {
    int client_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (client_socket < 0) {
        cerr << "Error creating socket." << endl;
        return -1;
    }

    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(vps_port);
    server_addr.sin_addr.s_addr = inet_addr(vps_ip.c_str());

    if (connect(client_socket, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        cerr << "Error connecting to server." << endl;
        return -1;
    }

    return client_socket;
}

// Function to send a frame to server
bool send_frame(int client_socket, const cv::Mat& frame) {
    vector<uchar> buffer;
    cv::imencode(".jpg", frame, buffer);
    uint32_t length = buffer.size();
    if (send(client_socket, &length, sizeof(length), 0) == -1) {
        cerr << "Error sending frame length." << endl;
        return false;
    }

    if (send(client_socket, buffer.data(), buffer.size(), 0) == -1) {
        cerr << "Error sending frame data." << endl;
        return false;
    }

    return true;
}

// Function to handle video streaming for a single camera
void stream_single_camera(const string& ip_address, const string& vps_ip, int vps_port, const string& cam_user, const string& cam_password) {
    string rtsp_address = "rtsp://" + cam_user + ":" + cam_password + "@" + ip_address + ":554/Streaming/Channels/102";
    cv::VideoCapture cap(rtsp_address);

    if (!cap.isOpened()) {
        cerr << "Failed to connect to the camera at " << ip_address << "." << endl;
        return;
    }

    while (true) {
        int client_socket = create_socket(vps_ip, vps_port);
        if (client_socket == -1) {
            cerr << "Connection failed for camera at " << ip_address << ", retrying in 5 seconds..." << endl;
            this_thread::sleep_for(chrono::seconds(5));
            continue;
        }

        cout << "Connected to server, starting video stream for camera at " << ip_address << "." << endl;

        try {
            while (true) {
                cv::Mat frame;
                cap >> frame;

                if (frame.empty()) {
                    cerr << "Error reading frame from camera at " << ip_address << ", resetting video capture." << endl;
                    cap.release();
                    this_thread::sleep_for(chrono::seconds(1));
                    cap.open(rtsp_address);
                    if (!cap.isOpened()) {
                        cerr << "Failed to re-open video capture." << endl;
                        break;
                    }
                    continue;
                }

                if (!send_frame(client_socket, frame)) {
                    cerr << "Socket lost for camera at " << ip_address << ", attempting to reconnect..." << endl;
                    break;
                }
            }
        } catch (const exception& e) {
            cerr << "Error during video streaming for camera at " << ip_address << ": " << e.what() << endl;
        } finally {
            close(client_socket);
        }

        cap.release();
        cout << "Video streaming ended for camera at " << ip_address << "." << endl;
    }
}

// Function to handle video streaming for multiple cameras using threading
void stream_multiple_cameras(const vector<string>& ip_list, const string& vps_ip, int vps_port, const string& cam_user, const string& cam_password) {
    vector<thread> threads;
    for (const auto& ip_address : ip_list) {
        threads.push_back(thread(stream_single_camera, ip_address, vps_ip, vps_port, cam_user, cam_password));
    }

    for (auto& th : threads) {
        th.join();
    }

    cout << "All video streams have ended." << endl;
}

int main() {
    string vps_ip = "160.22.122.122";
    int vps_port = 8000;
    string cam_user = "admin";
    string cam_password = "CamProject12";

    // Get host IP and determine the network range
    string host_ip = get_host_IP();
    string network_range = convert_to_CIDR(host_ip);

    // Get the list of camera IPs
    vector<string> list_ip_address = get_list_camera_IP(network_range);

    if (!list_ip_address.empty()) {
        // Start streaming from the first camera
        stream_single_camera(list_ip_address[0], vps_ip, vps_port, cam_user, cam_password);
    } else {
        cout << "No cameras found!" << endl;
    }

    return 0;
}
