# Keystroke Dynamics Authentication Prototype

A desktop prototype for biometric user authentication based on **keystroke dynamics**.
The application analyzes the way a user types a fixed string by measuring timing-based behavioral features such as **dwell time**, **flight time**, and **total typing time**.

The goal of the project is to demonstrate how typing rhythm can be used as an additional authentication factor without requiring specialized biometric hardware.

## Overview

Keystroke dynamics is a behavioral biometric method that identifies users based on their typing patterns.
Even when two users type the same password or phrase, the timing of their key presses and releases can differ significantly.

This project implements a static authentication system where:

1. A user creates a profile by typing a fixed phrase several times.
2. The system extracts timing features from each sample.
3. A biometric profile is built using averages and standard deviations.
4. During login, a new typing sample is compared against the stored profile.
5. Access is granted or denied based on a calculated similarity score and an individual threshold.

## Features

* User enrollment with multiple training samples
* Static keystroke dynamics authentication
* Measurement of:

  * dwell time
  * flight time
  * total typing time
  * key press offsets
* Individual authentication threshold for each user
* Weighted similarity score calculation
* Password/fixed-text validation before biometric comparison
* Local user profile storage in JSON format
* Tkinter-based graphical user interface
* Timeline visualization of the latest typing sample
* Protection against invalid samples caused by paste, cut, Ctrl combinations, Backspace, or Delete

## Technologies Used

* Python
* Tkinter / ttk
* Dataclasses
* JSON file storage
* SHA-256 hashing
* Statistical feature extraction

## Project Structure

```text
Keystroke_dynamics/
│
├── backend.py          # Core authentication logic and profile handling
├── main.py             # Graphical interface and keyboard event recording
├── users.json          # Generated automatically after user enrollment
└── README.md
```

## How It Works

### 1. Data Collection

During enrollment or authentication, the application records the exact time of each key press and key release.

For every key, the system creates a time interval containing:

```text
press_time_ms
release_time_ms
```

These intervals are then used to calculate the biometric features.

### 2. Feature Extraction

The system extracts several timing-based features.

**Dwell time** measures how long a key is held:

```text
dwell_time = release_time - press_time
```

**Flight time** measures the time between releasing one key and pressing the next:

```text
flight_time = next_press_time - current_release_time
```

**Total typing time** measures how long it takes to type the full fixed phrase:

```text
total_typing_time = last_release_time - first_press_time
```

### 3. User Profile Creation

During enrollment, the user types the same fixed text multiple times.
The application builds a biometric profile by calculating:

* mean dwell time vector
* standard deviation dwell time vector
* mean flight time vector
* standard deviation flight time vector
* average total typing time
* standard deviation of total typing time
* individual acceptance threshold

The default minimum number of enrollment samples is:

```python
MIN_ENROLLMENT_SAMPLE_COUNT = 6
```

### 4. Authentication

During login, the user first enters the correct fixed text.
If the text matches, the system compares the new typing sample with the stored biometric profile.

The comparison is based on normalized distances:

```text
distance = abs(current_value - mean_value) / standard_deviation
```

The final authentication score is calculated using weighted components:

```python
DWELL_TIME_WEIGHT = 0.50
FLIGHT_TIME_WEIGHT = 0.30
TOTAL_TIME_WEIGHT = 0.20
```

If the final score is lower than or equal to the user’s individual threshold, access is granted.
If the score is higher than the threshold, access is denied.

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/keystroke-dynamics.git
cd keystroke-dynamics
```

No external Python packages are required.
The project uses Python’s standard library and Tkinter.

Run the application:

```bash
python main.py
```

Depending on your system, you may need to use:

```bash
python3 main.py
```

## Usage

### Enrollment

1. Open the **Training** tab.
2. Enter a username.
3. Enter a fixed text/password with at least 10 characters.
4. Click **Start Training**.
5. Type the fixed text 6 times.
6. Save each valid sample.
7. After the final sample, the user profile is created automatically.

### Authentication

1. Open the **Authentication** tab.
2. Select or enter the username.
3. Type the same fixed text/password.
4. Click **Authenticate**.
5. The system will compare the current typing pattern with the saved profile.
6. The result will show whether access is granted or denied.

## Example Results

During testing, the system was able to distinguish between legitimate and illegitimate login attempts based on typing behavior.

Example successful authentication:

```text
Similarity score: 0.68
Authentication threshold: 1.80
Result: Access granted
```

Example failed authentication:

```text
Similarity score: 2.80
Authentication threshold: 1.80
Result: Access denied
```

In a small test with two users:

| Test Type                                   | Attempts | Successful | Failed |
| ------------------------------------------- | -------: | ---------: | -----: |
| Legitimate user accessing own profile       |       10 |          9 |      1 |
| Illegitimate user accessing another profile |       10 |          2 |      8 |

Calculated metrics:

```text
FRR = 10%
FAR = 20%
```

These results show that the prototype can detect differences in typing behavior, but it should be treated as an educational demonstration rather than a production-ready authentication system.

## Security Considerations

Keystroke dynamics can be useful as an additional authentication layer, but it should not be used as the only security mechanism in real-world systems.

Possible limitations and risks include:

* typing behavior can change due to stress, fatigue, injury, or keyboard changes
* an attacker may attempt to imitate the typing rhythm of another user
* malware or keyloggers could capture both text and timing data
* fixed-text authentication is less flexible than dynamic challenge-based authentication
* the current prototype stores user profiles locally

For stronger security, this method should be combined with other authentication factors.

## Possible Improvements

Future improvements could include:

* support for dynamic text challenges
* more advanced anomaly detection algorithms
* larger user testing dataset
* adaptive profile updates over time
* encrypted local profile storage
* separation of biometric profile and password storage
* export of test results and metrics
* comparison of different threshold calculation methods
* support for continuous authentication during a session

## Educational Purpose

This project was developed as a university prototype for studying biometric authentication through keystroke dynamics.
It demonstrates the basic principles of behavioral biometrics, feature extraction, statistical user profiling, and threshold-based authentication decisions.

## Disclaimer

This application is a prototype and is not intended for production use.
It is designed for educational and experimental purposes only.
