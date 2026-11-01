# Wearable Human Activity Recognition System

**Embedded Systems · Wearable Technology · IMU-Based Sensing · Wi-Fi Communication · Deep Learning**

<p align="center">
  <img src="images/device.jpg" alt="Wearable Human Activity Recognition Device" width="500">
</p>

## Project Overview

This project presents a wearable Human Activity Recognition (HAR) system designed to identify human physical activities using inertial sensor data and deep learning.

The system combines an ESP32-C3 microcontroller with an MPU6050 six-axis inertial measurement unit (IMU) to acquire real-time motion data. The collected data is transmitted wirelessly over Wi-Fi to a Python-based desktop application, where a trained 1D Convolutional Neural Network (1D-CNN) classifies the user's activity.

The system is designed to demonstrate the integration of embedded hardware, wireless communication, real-time data acquisition, signal processing, and machine learning in a wearable application.

## System Architecture

The system consists of three main components:

1. **Wearable Hardware:** An ESP32-C3 microcontroller interfaced with an MPU6050 sensor for motion data acquisition.
2. **Wireless Communication:** Wi-Fi Access Point and TCP socket communication for transmitting sensor measurements to a computer.
3. **Machine Learning Application:** A Python desktop application that processes incoming sensor data and performs real-time activity classification using a trained 1D-CNN model.

## Supported Activities

The trained model recognizes seven different activity classes:

| Label | Activity |
|:---:|---|
| 0 | Cycling |
| 1 | Downstairs |
| 2 | Jogging |
| 3 | Typing |
| 4 | Upstairs |
| 5 | Walking |
| 6 | Writing |

## Hardware Specifications

| Component | Description |
|---|---|
| Microcontroller | ESP32-C3 Super Mini |
| Motion Sensor | MPU6050 |
| Sensor Interface | I²C |
| Wireless Communication | Wi-Fi |
| Data Transmission | TCP Socket |
| Accelerometer Range | ±2g |
| Gyroscope Range | ±250 °/s |
| Sampling Frequency | 20 Hz |
| I²C Clock Frequency | 400 kHz |

## Data Acquisition and Communication

The MPU6050 provides six-axis motion measurements:

- Three-axis acceleration: X, Y, and Z
- Three-axis angular velocity: X, Y, and Z

The ESP32-C3 operates as a Wi-Fi Access Point and provides a TCP server for receiving connections from the desktop application.

The communication configuration is:

| Parameter | Value |
|---|---|
| Wi-Fi SSID | `ESP32-C3-MPU6050` |
| Wi-Fi Password | `mpu6050wifi` |
| TCP Server IP | `192.168.4.1` |
| TCP Server Port | `3333` |
| Data Format | `ax, ay, az, gx, gy, gz` |

Acceleration values are initially transmitted in units of g, while angular velocity values are transmitted in degrees per second.

The desktop application converts the measurements into SI units before model inference.

## Machine Learning Model

A one-dimensional Convolutional Neural Network (1D-CNN) is used to recognize human activities from the acquired motion signals.

The model receives a six-channel time-series input with the following dimensions:

- Window length: 40 samples
- Number of channels: 6
- Window duration: 2 seconds
- Sampling frequency: 20 Hz

The CNN architecture includes:

- 1D Convolutional layers
- Batch Normalization
- Max Pooling
- Dropout
- Fully Connected layers
- Softmax output layer

The final layer produces probabilities for the seven activity classes.

## Model Performance

The reported offline evaluation achieved an accuracy of **95.86%** on 3,911 evaluation windows.

This result represents the evaluation procedure described in the project report. Since overlapping windows were generated before a random window-level split, and the evaluation data was also used during validation, the reported accuracy may be affected by data leakage. Therefore, it should not be interpreted as a subject-independent generalization result.

The classification performance also varies across activity classes, with lower recall reported for some activities, particularly Upstairs and Downstairs.

## Dataset

The project uses the BandX-Activity dataset.

Dataset source:

[BandX-Activity Dataset – Zenodo](https://doi.org/10.5281/zenodo.14543551)

The dataset contains motion recordings from 33 participants and is described in the project report as being sampled at 20 Hz.
