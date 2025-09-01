# Extract-Raspberry

![Alt text](./images/image_2.png)

## 📋 Description

This project implements a Web Server with FastAPI to monitor Raspberry Pi data, such as RAM and ROM usage, temperature and other system metrics. The information is accessed via HTTP request, returning a JSON with the board data.

## 🚀 Features

- System Temperature Monitoring – Provides real-time CPU and GPU temperature data to prevent overheating.

- Disk Usage Statistics – Displays available storage, used space, and partition details.

- Memory Utilization – Tracks RAM usage, including free, used, and cached memory.

- CPU Performance Metrics – Monitors processor load, usage percentage, and active processes.

- Uptime & System Health – Reports how long the device has been running and overall system status.

- Lightweight & Efficient – Optimized to run on Raspberry Pi with minimal resource consumption.

## 🛠️ Technologies Used

- **Raspberry Pi 4** 
- **FastApi**

## 📦 Installation

### Requirements

- Python 3.x
- Raspberry Pi
- Distro Linux Raspberry : Raspbian

### Installation Steps

1. Clone the repository:
    ```bash
    git clone https://github.com/IsaacMartins12/Extract-Raspberry
    ```

2. Create virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows: venv\Scripts\activate


3. Install dependencies:
    ```bash
    python install -r requirements.txt

4. Run the main app:
    ```bash
    run server.py

## 🧑‍💻 Contribution

We welcome contributions to improve this project. Feel free to submit pull requests or report issues on the [Issues page](https://github.com/IsaacMartins12/Smart-Energy-Meter/issues).

### Contribution Steps

1. Fork the project.
2. Create a branch for your feature (`git checkout -b feature/new-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-feature`).
5. Create a Pull Request with a detailed description of your changes.

## 📜 License

This project is licensed under the [MIT License](LICENSE).

