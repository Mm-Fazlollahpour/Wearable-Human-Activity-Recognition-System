# Hardware Design

This directory contains the hardware-related information for the Wearable Human Activity Recognition System.

The wearable device is built around an ESP32-C3 microcontroller and an MPU6050 six-axis inertial measurement unit (IMU).

## Main Components

### ESP32-C3 Super Mini

The ESP32-C3 is the main controller of the wearable system.

Its responsibilities include:

- Communicating with the MPU6050 through I²C.
- Acquiring accelerometer and gyroscope measurements.
- Configuring the Wi-Fi Access Point.
- Establishing a TCP server for wireless data transmission.
- Sending sensor measurements to the desktop application.

### MPU6050

The MPU6050 is a six-axis motion tracking sensor that integrates:

- Three-axis accelerometer.
- Three-axis gyroscope.

It provides the motion measurements required for human activity recognition.

## Hardware Configuration

| Parameter | Configuration |
|---|---|
| Microcontroller | ESP32-C3 Super Mini |
| IMU Sensor | MPU6050 |
| Communication Interface | I²C |
| I²C Clock | 400 kHz |
| Accelerometer Range | ±2g |
| Gyroscope Range | ±250 °/s |
| Sampling Frequency | 20 Hz |
| SDA | GPIO 8 |
| SCL | GPIO 9 |

## Pin Connections

| MPU6050 Pin | ESP32-C3 Pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| SDA | GPIO 8 |
| SCL | GPIO 9 |

## Sensor Configuration

The MPU6050 is configured to acquire acceleration and angular velocity data.

The configuration described in the project includes:

- Accelerometer full-scale range: ±2g
- Gyroscope full-scale range: ±250 °/s
- Digital Low-Pass Filter configuration: 3
- Sample Rate Divider: 49
- I²C communication frequency: 400 kHz

## Wireless Communication

The ESP32-C3 operates as a Wi-Fi Access Point.

The desktop application connects to the device and receives the sensor measurements through a TCP socket.

| Parameter | Value |
|---|---|
| SSID | `ESP32-C3-MPU6050` |
| Password | `mpu6050wifi` |
| IP Address | `192.168.4.1` |
| TCP Port | `3333` |

## Hardware Operation

The hardware operates according to the following sequence:

1. The ESP32-C3 initializes the MPU6050.
2. The sensor starts providing six-axis motion measurements.
3. The ESP32-C3 samples the sensor data at the configured rate.
4. The microcontroller establishes its Wi-Fi Access Point and TCP server.
5. The acquired measurements are transmitted to the connected computer.
6. The desktop application processes the incoming data.

## Hardware Resources

Hardware photographs and related visual documentation are available in the `images/` directory.

For a visual overview of the assembled device, see the main project README.
