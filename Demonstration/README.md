# Project Demonstration

This directory contains demonstration materials showing the operation of the Wearable Human Activity Recognition System.

The demonstration is intended to illustrate the complete workflow, from wearable motion sensing to real-time activity classification.

## Demonstration Workflow

The system demonstration covers the following stages:

1. Powering on the wearable device.
2. Connecting the computer to the ESP32-C3 Wi-Fi Access Point.
3. Establishing the TCP communication link.
4. Acquiring real-time six-axis motion data from the MPU6050.
5. Processing incoming sensor measurements.
6. Preparing input windows for the trained CNN model.
7. Performing activity classification.
8. Displaying the predicted activity in the desktop application.

## Supported Activities

The system recognizes the following seven activities:

- Cycling
- Downstairs
- Jogging
- Typing
- Upstairs
- Walking
- Writing

## Demonstration Files

Place project demonstration videos and related materials in this directory.

Suggested filenames:

```text
demonstration/
├── README.md
└── device_operation.mp4
