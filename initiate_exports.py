from download_reports import *
import pandas as pd
import os
from time import sleep
from random import randint
import sys

def get_exports(group_list, course, username, password):
    '''
    Handler function. Creates selenium instance, signs in then proceeds to open
    every download link scraped via email, beginning file download. Calls
    __move_files to sort files for later processing
    '''
    url ='https://programs.techstewardship.com/manage/reports'
    driver, wait, actions = setup(headless=False, download_dir=f"{os.path.join('.', 'Downloaded Reports')}", browser='Firefox')
    signin(driver, username, password)
    sleep(2)
    __progress(driver, wait, course)
    print('Progress Report retrieved...')
    link_list = __groups(group_list, driver, wait)
    print('Group links retrieved. Generating export emails...')
    __open_group_links(driver, link_list)


def __progress(driver, wait, course):
    url ='https://programs.techstewardship.com/manage/reports'
    driver.get(url)
    courses = driver.find_elements(By.XPATH, '//*[@id="main-content"]/div[4]/div/div/div/table/tbody/tr')

    for index, _ in enumerate(courses):
        ts_course = driver.find_element(By.XPATH, f'//*[@id="main-content"]/div[4]/div/div/div/table/tbody/tr[{index+1}]/td[1]')
        if course.name == ts_course.text:
            driver.find_element(By.XPATH, f'/html/body/main/div[4]/div/div/div/table/tbody/tr[{index+1}]/td[2]/div/div/a').click()
            wait.until(EC.presence_of_element_located((By.XPATH, f'/html/body/main/div[5]/div[1]/div/a[3]'))).click()


def __groups(group_list, driver, wait):
    url ='https://programs.techstewardship.com/manage/reports/groups'
    driver.get(url)
    groups = driver.find_elements(By.XPATH, '//*[@id="main-content"]/div[4]/div/div/div/table/tbody/tr')
    print(f'{len(groups)} groups found!')
    link_list = []
    for index, group in enumerate(groups):

        # Extracting group name from element
        group_name = group.text.split('\n')[0]

        if group_name in group_list:

            element = driver.find_element(By.XPATH, f'/html/body/main/div[4]/div/div/div/table/tbody/tr[{index+1}]/td[2]/div/div/button')
            driver.execute_script("arguments[0].scrollIntoView();", element)
            link = driver.find_element(By.XPATH, f'//*[@id="main-content"]/div[4]/div/div/div/table/tbody/tr[{index+1}]/td[2]/div/div/div/a').get_attribute('href')

            #LINK NOW NOT INCLUDING CSV EXTENSIONS
            link_list.append(f'{link}.csv')

    return link_list


def __open_group_links(driver, link_list):
    print(f'{len(link_list)} links retrieved!')
    for i, link in enumerate(link_list):
        sys.stdout.write(f"Generating exports: Link {i+1}/{len(link_list)}   \r")
        sys.stdout.flush()
        driver.get(link)
        sleep(0.05)
