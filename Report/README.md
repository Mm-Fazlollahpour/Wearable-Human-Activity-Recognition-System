# Technical Project Report

This directory contains the technical report documenting the design, implementation, and evaluation of the Wearable Human Activity Recognition System.

The report presents the theoretical background, hardware architecture, embedded software, wireless communication, machine learning implementation, and experimental results.

## Project Description

The project focuses on developing a wearable Human Activity Recognition system using inertial motion sensing and deep learning.

An ESP32-C3 microcontroller interfaces with an MPU6050 six-axis IMU to acquire real-time acceleration and angular velocity measurements.

The acquired data is transmitted wirelessly to a computer, where a Python application processes the signals and performs activity classification using a trained one-dimensional Convolutional Neural Network.

## Report Contents

The technical documentation covers the following main topics:

### 1. Introduction

- Human Activity Recognition fundamentals.
- Wearable sensing systems.
- Applications of motion-based activity recognition.
- Overview of the proposed system.

### 2. Hardware Design

- ESP32-C3 microcontroller.
- MPU6050 inertial measurement unit.
- I²C communication interface.
- Sensor configuration.
- Hardware implementation and integration.

### 3. Embedded Software

- Sensor initialization.
- Motion data acquisition.
- Sampling configuration.
- Wi-Fi Access Point implementation.
- TCP communication.
- Real-time data transmission.

### 4. Dataset and Signal Processing

- BandX-Activity dataset.
- Motion signal preparation.
- Six-axis sensor measurements.
- Input window generation.
- Data preprocessing.

### 5. Machine Learning Implementation

- 1D Convolutional Neural Network.
- Model architecture.
- Training procedure.
- Activity classification.
- Model evaluation.

### 6. Desktop Application

- Python application development.
- TCP client implementation.
- Real-time sensor data reception.
- Neural network inference.
- Graphical user interface.

### 7. Experimental Results

- System operation.
- Activity recognition results.
- Model performance.
- Evaluation accuracy.
- Discussion of classification performance.

## Main System Specifications

| Parameter | Value |
|---|---|
| Microcontroller | ESP32-C3 Super Mini |
| Motion Sensor | MPU6050 |
| Communication | Wi-Fi / TCP |
| Sampling Frequency | 20 Hz |
| Input Window | 40 × 6 |
| Window Duration | 2 seconds |
| Classification Model | 1D-CNN |
| Number of Classes | 7 |
| Reported Offline Accuracy | 95.86% |

## Related Project Resources

The implementation files associated with this report are organized as follows:

| Directory | Description |
|---|---|
| `../hardware/` | Hardware components and configuration |
| `../software/` | Embedded and desktop software |
| `../model/` | Dataset processing and machine learning |
| `../images/` | Project photographs and visual documentation |
| `../demonstration/` | Demonstration materials |

## Report File

The complete project report is available in this directory.

For detailed implementation descriptions, design decisions, technical specifications, and experimental results, refer to the main report document.
