# TS_Automation

This is a Python script that automates several tasks related to managing the Tech Stewardship program. It was developed to help streamline the administrative processes involved in managing the program, including collecting survey data, generating progress reports, and organizing program files.

## Getting Started
Prerequisites
Before running the script, you'll need to have the following installed:

- Python 3.x
- Selenium WebDriver
- Pandas
-

## Configuration
Before running the script, you'll need to set up a few configuration variables:

DRIVER_PATH: The file path to your local Selenium WebDriver executable.
DOWNLOAD_DIR: The file path to the directory where program reports and files will be downloaded.
USERNAME: Your Tech Stewardship program username.
PASSWORD: Your Tech Stewardship program password.
You can set these variables by modifying the values in the config.py file.

## Usage

To operate the script, there are 3 configurations in which the report generation can be performed:

1. Full report generation that will automate all retrieval of exports and survey data
```
python construct.py -e
```
2. Report generation without export retrieval, reading existing exports available via SMTP
```
python construct.py
```
3. Report generation using only locally downloaded exports (primarly for testing or quick regeneration)
```
python construct.py -n
```


This will initiate the program and begin the automated tasks.

Functionality
The Tech Stewardship Automation Script currently provides the following functionality:

1. If exports are requested, the script will launch the Tech Stewardship page via browser and trigger all exports for the required groups. Full exports including individual group reports are generated and sent via email.
2. If the script is run with no command line arguments, it will begin at this portion of the process and extract all exports from the TS email account being exported to. 
3. If script is run with '-n', then only existing files in the local directory will be used at this point.
4. All data from Thinkific, TypeForm, and Attendance data is computed to created a comprehensive list of every student's performance across platforms, subdivided by their group (school or course).






