from selenium_setup import *
import pandas as pd
import csv
import os
from time import sleep
from random import randint


def signin(driver, username, password):
    '''
    This function signs into the Tech Stewardship website using the provided login credentials.

    Args:
    driver (WebDriver): The WebDriver object for the Chrome browser.
    username (str): The email address associated with the user's account.
    password (str): The password associated with the user's account.
    '''

    link ='https://programs.techstewardship.com/users/sign_in'
    driver.get(link)
    driver.find_element(By.XPATH, '//*[@id="user[email]"]').send_keys(username)
    sleep(1)
    submit = driver.find_element(By.XPATH, '//*[@id="user[password]"]')
    sleep(1)
    submit.send_keys(password)
    sleep(1)
    driver.find_element(By.XPATH, '/html/body/main/div/div/article/form/div[5]/button').click()
    sleep(2)
    if driver.current_url == 'https://programs.techstewardship.com/users/sign_in':
        input('Press any key to continue')
    print('SIGN IN COMPLETE.\n')



def __move_files(entry, course_name, downloaded_filename):
    '''
    This function sorts through various downloaded files, names them and organizes them accordingly.

    Args:
    entry (tuple): A tuple of the download link and filename.
    course_name (str): The name of the course for which the file is being downloaded.
    downloaded_filename (str): The name of the file that has been downloaded.
    '''

    subject = entry[1]
    print(f'Renamed {subject}\n')

    tmp = subject.lower().split(': ')[1].split(' for ')
    report_type = tmp[0].title()

    if report_type == 'Users':
        new_filename = 'User Report.csv'
    else:
        report_name = tmp[1].replace("\r\n", "").title()
        if not course_name.lower() == report_name.lower() and not 'survey results' in subject.lower():
            new_filename = f'Group_{report_type}_{report_name}.csv'
        else:
            new_filename = f'{report_type}_{report_name}.csv'

    os.rename(os.path.join('Downloaded Reports', downloaded_filename), os.path.join(course_name, 'Downloaded Reports', new_filename))


def get_downloads(files, username, password, course_name):
    '''
    This function logs in to the Tech Stewardship website using the provided credentials, downloads the files
    specified in the input list of tuples, and saves them in the appropriate directory.

    Args:
    files (List[Tuple[str,str]]): A list of tuples, where each tuple contains a download link and a filename.
    username (str): The email address associated with the user's account.
    password (str): The password associated with the user's account.
    course_name (str): The name of the course for which the files are being downloaded.
    '''
    driver, wait, actions = setup(headless=False, download_dir=f"{os.path.join('.', 'Downloaded Reports')}")
    signin(driver, username, password)
    sleep(2)


    for entry in files:

        link = entry[0]
        old_filenames = set(os.listdir('Downloaded Reports'))
        driver.get(link)
        print(f'Downloaded {entry[1]}')
        downloaded = False
        sleep(1)

    
        while downloaded is False:
            current_filenames = set(os.listdir('Downloaded Reports'))
            num_files = len(current_filenames - old_filenames) == 1
            not_downloaded = any(filename.endswith('.crdownload') for filename in current_filenames - old_filenames)
            # Check if a new file has been added to the directory
            if len(current_filenames - old_filenames) == 1 and not not_downloaded:
                downloaded = True
                downloaded_filename = list(current_filenames - old_filenames)[0]

        __move_files(entry, course_name, downloaded_filename)

