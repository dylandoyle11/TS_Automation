import pandas as pd
from credentials import login_credentials
from download_reports import *
from initiate_exports import *
import imaplib
import email
import re
import os
from thinkific import Thinkific
from pathlib import Path
import argparse
import inquirer
import gspread
from gspread_dataframe import set_with_dataframe
from datetime import datetime
from functools import reduce
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import pyfiglet
import requests


LOGIN_DICT = login_credentials()
COURSE_CONFIG_URL = 'https://docs.google.com/spreadsheets/d/1agtq7aPw_LUce7b3rYv7LKs40oqo0cj0z50HQ-r9EYM/edit#gid=0'
PARTICIPANT_CONFIG_URL = 'https://docs.google.com/spreadsheets/d/1ipe43_HfpbR25DSz13JIZq1sF4fYck3qPyVcqM49T74/edit#gid=0'


class Course():
    """
    Course object that represents currently ongoing course in question
    """
    def __init__(self, name, data_url, attendance_url, thinkific_url, master_url, credential_url):
        self.name = name
        self.data_url = data_url
        self.attendance_url = attendance_url
        self.thinkific_url = thinkific_url
        self.master_url = master_url
        self.participant_config_url = 'https://docs.google.com/spreadsheets/d/1ipe43_HfpbR25DSz13JIZq1sF4fYck3qPyVcqM49T74/edit#gid=0'
        self.credential_url = credential_url

class Group():
    '''
    Group object consisting of student emails
    '''
    def __init__(self, df, filename):
        self.name = filename
        self.emails = df['Email'].tolist()


def create_course(course_config_url, thinkific, gc):
    '''
    Connects to the config file in gsheets, prompts the user to select the appropriate course,
    then selects all relevant information and creates a course object.

    Args:
    course_config_url (str): The URL of the course configuration file in Google Sheets.
    thinkific (Thinkific): An instance of the Thinkific API client.
    gc (gspread.client.Client): An authenticated instance of the Google Sheets client.

    Returns:
    Course: The course object.
    '''

    # Connect to gc
    
    config = gc.open_by_url(course_config_url).worksheet('Sheet1')
    config_df = pd.DataFrame(config.get_all_records())
    course_list = config_df['Course Name'].tolist()

    if len(course_list) == 1:
        course_name = course_list[0]
    else:
        # Select course through terminal
        course_name = __select_course(course_list)

    # Select row from config file and retrieve relevant info
    df = config_df.loc[config_df['Course Name'] == course_name].reset_index()
    name = df['Course Name'][0]
    data_url = df['Answers URL'][0]
    attendance_url = df['Attendance URL'][0]
    thinkific_url = df['Thinkific URL'][0]
    master_url = df['Master File URL'][0]
    credential_url = df['Credential Status URL'][0]

    # Retrieve relevant course info from thinkific and construct object
    t_courses = thinkific.courses.list()
    for course in t_courses['items']:

        # Check course exists on thinkfic
        name = course['name']
        
        if course_name == name:
            course_object = Course(name, data_url, attendance_url, thinkific_url, master_url, credential_url)
            break

    try:
        return course_object

    except UnboundLocalError:
        print('NO COURSE FOUND. EXITING PROGRAM.\n')
        quit()


def __select_course(courses):
    '''
    Prompts the user to select a course from the provided list.

    Args:
    courses (List[str]): A list of course names to select from.

    Returns:
    str: The selected course name.
    '''
    q = [inquirer.List('course', message="Select Course", choices=[course for course in courses])]
    answers = inquirer.prompt(q)
    
    return list(answers.items())[0][1]


def gspread_authenticate():
    '''
    Authenticates with Google Sheets API and returns the authenticated client.

    Returns:
    gspread.client.Client: The authenticated Google Sheets client.
    '''
    DEFAULT_SCOPES =[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    gc = gspread.oauth(scopes=DEFAULT_SCOPES)

    return gc


def get_email_link(username, password, course):
    '''
    Retrieves download links from email and returns a list of tuples containing the link and the email subject.

    Args:
    username (str): The email username.
    password (str): The email password.
    course (Course): The course object.

    Returns:
    List[Tuple[str, str]]: A list of tuples containing the download link and email subject.
    '''

    # create regex to recognize download links within email html
    regex = '(?:Click here)(?:.*\n)(?:\(\s)([\s\S]*)(?:\s\)\n\s)(?:to download)'
    name_regex = '(:?Survey Results For\s)(.*\s.*\d\d\d\d)(\s-\s.*)'
    # create imap instance
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(username, password)
    mail.select()
    print('Retreiving reports via email...')

    #id holds numerical value locations of emails found
    typ, message_id = mail.search(None, '(SUBJECT "Export")', '(UNSEEN FROM "Thinkific")')
    if len(message_id[0].split()) < 1:
        print('NO EMAILS FOUND... EXITING PROGRAM.')
        exit()

    # Create lists holding the url, email subject and filenames to be zipped later
    links = []
    subjects = []
    filenames = []

    for num in message_id[0].split():
        typ, data = mail.fetch(num, '(RFC822)')
        email_message = data[0][1].decode('utf-8')
        email_message = email.message_from_string(email_message)
        subject = email_message.get('subject')
        subjects.append(subject)


        # If course does not match course reported in exports, exit
        if 'Survey Results' in subject:

            subject = repr(r"{}".format(subject).replace('\r\n', ''))
            course_name = re.search(name_regex, subject).group(2)
            if course.name != course_name:
                print('INCORRECT COURSE DETECTED - EXITING PROGRAM')
                exit(1)

        # Iterate through email content
        for part in email_message.walk():
            # find plain text content
            if part.get_content_type() == 'text/plain':

                # If regex fails, email is not an export link
                try:
                    link = re.search(regex, str(part)).group(1)
                    link = r'{}'.format(link).replace('\r\n', '').replace('=\n', '')
                except AttributeError:
                    print(f'Invalid email detected - SKIPPING {part}')
                    continue

                links.append(link)
                print(f"{len(links)} Links Added!", end='\r', flush=True)


        # Create nested list of downloaded file info
        files = list(zip(links, subjects))

    mail.close()
    mail.logout()
    return files


def create_groups(course):
    '''
    Uses the Thinkific group reports to create a list of Group objects.

    Args:
    course (Course): The course object.

    Returns:
    List[Group]: A list of Group objects.
    '''
    group_list = []
    for file in os.listdir(os.path.join(course.name, 'Downloaded Reports')):
        if file.startswith('Group'):
            df = pd.read_csv(os.path.join(course.name, 'Downloaded Reports', file))
            group_name =  re.sub(r'.csv$', '', file.split('_')[-1])

            try:
                group_list.append(Group(df, group_name))
            except KeyError:
                print(f'Unknown Format Detected - Skipping file named:\n"{file}"')

    return group_list


def __get_progress_report(course):
    '''
    Helper function to select the course progress report and create a pandas dataframe.

    Args:
    course (Course): The course object.

    Returns:
    pd.DataFrame: The progress report as a pandas dataframe.
    '''


    for file in os.listdir(os.path.join(course.name, 'Downloaded Reports')):
        # Check file is progress report and course name matches
        if file.startswith('Progress Report') and course.name.lower() == file.split('_')[-1].strip('.csv').lower():
            progress_df = pd.read_csv(os.path.join(course.name, 'Downloaded Reports', file))

    return progress_df


def generate_prog_reports(course, groups):
    '''
    Separates reporting into groups and generates a master progress report.

    Args:
    course (Course): The course object.
    groups (List[Group]): A list of Group objects.

    Returns:
    pd.DataFrame: The master progress report as a pandas dataframe.
    '''
    progress_df = __get_progress_report(course)
    master_progress = pd.DataFrame()

    for group in groups:

        # Match emails from group emails to progress reports and obtain records
        df = progress_df.loc[progress_df['Email'].isin(group.emails)].reset_index(drop=True).sort_values(by='Last Name')
        df['Group'] = group.name
        
        # Add group reports to master report
        master_progress = pd.concat([master_progress, df], ignore_index=True)

    master_progress.to_csv(os.path.join(course.name, 'Reports', 'Master Progress Report.csv'), index=None)
    master_progress.to_csv('prog.csv')
    return master_progress



def get_reporting_groups(gc, course):  
    '''
    Extracts a list of groups requiring partner reporting from the participant configuration sheet.

    Args:
    gc (gspread.client.Client): An authenticated instance of the Google Sheets client.
    course (Course): The course object.

    Returns:
    Tuple[pd.DataFrame, List[str]]: A tuple containing the partner reporting dataframe and a list of participant groups.
    '''
    sheet = gc.open_by_url(course.participant_config_url).worksheet('Sheet1')
    df = pd.DataFrame(sheet.get_all_records())
    partner_reporting_df = df[df[course.name].str.startswith('https://drive.google.com/drive/')]
    participant_group_list = df[df[course.name] == 'x']['Group'].tolist()

    return partner_reporting_df, participant_group_list


def __get_attendance(course, gc):
    '''
    Adds attendance data to the master progress report.

    Args:
    master_progress (pd.DataFrame): The master progress report as a pandas dataframe.
    course (Course): The course object.
    gc (gspread.client.Client): An authenticated instance of the Google Sheets client.

    Returns:
    pd.DataFrame: The updated master progress report as a pandas dataframe.
    '''
    # Create blank df
    att_df = pd.DataFrame(columns=['First name', 'Last name', 'Email', 'Submitted At', 'Date'])
    attendance = gc.open_by_url(course.attendance_url)
    attendance_date_list = []

    # Iterate through each attendance sheet
    for sheet in attendance.worksheets():
        date = str(sheet.title).strip('TSPS - ')
        attendance_date_list.append(date)
        df = pd.DataFrame(sheet.get_all_records())
        if df.shape[0] == 0:
            continue
        entry = df[['First name', 'Last name', 'Email', 'Submitted At']].copy()
        entry['Date'] = date
        att_df = pd.concat([att_df, entry])

    return att_df, attendance_date_list


def add_attendance(master_progress, course, gc):
    """
    Adds attendance information to a master progress DataFrame.
    
    This function takes a master progress DataFrame (master_progress), a course object (course), and a 
    Google Sheets client object (gc) as input. It uses the course object and the Google Sheets API to 
    retrieve attendance data for the specified course, and matches the attendance data with the email 
    addresses in the master progress DataFrame. The attendance count and attendance dates are added 
    to the master progress DataFrame as new columns.
    
    Args:
    master_progress (pd.DataFrame): The master progress DataFrame to which attendance data will be added.
    course (Course): A course object containing the name and URL of the course being processed.
    gc (gspread.client.Client): A Google Sheets client object used to retrieve attendance data from the course.
    
    Returns:
    pd.DataFrame: The modified master progress DataFrame with attendance data added.
    """

    att_df, attendance_date_list = __get_attendance(course, gc)
    for index, row in master_progress.iterrows():
        email = row['Email']
        # if email == 'snali@mun.ca':
        #     print('my man')
        # Match emails to list of full attendance to extract drop-ins,
        # use set() due to duplicates in attendace
        att_list = set(att_df.loc[att_df['Email'] == email]['Date'].values)
        attendance_counter = len(att_list)

        master_progress.at[index, 'Attendance Count'] = attendance_counter
        for date in att_list:
            master_progress.at[index, f'Attendance - {date}'] = 'ATTENDED'

    # master_progress.to_csv('att.csv')
    return master_progress


def concat_answers(df, module_name):
    """
    Concatenates specific columns of a DataFrame based on the given module name based on reporting requirements.
    
    This function takes a DataFrame (df) and a module name (module_name) as input, and concatenates the 
    content of specific columns for each row depending on the module name. The concatenated answers are 
    stored in a new column called 'concat_answers' in the DataFrame.
    
    Args:
    df (pd.DataFrame): The input DataFrame containing the data to be processed.
    module_name (str): The name of the module used to determine which columns to concatenate.
    
    Returns:
    pd.DataFrame: The modified DataFrame with the new 'concat_answers' column containing the concatenated answers.
    """
    #apply lower() for better string matching
    module_name = module_name.lower()

    if 'share a story' in module_name:
        concat_list = ['what kind of story do you want to share this week?', 'describe the situation', 'how does', 'what opportunities']
        df['concat_answers'] = df.apply(lambda x: ' '.join(x[col] for col in df.columns if any(term in col.lower() for term in concat_list)), axis=1)

    elif 'advance understanding' in module_name or 'deliberate values' in module_name:
        concat_list = ['what questions are you currently', 'what stood', 'how was']
        df['concat_answers'] = df.apply(lambda x: ' '.join(x[col] for col in df.columns if any(term in col.lower() for term in concat_list)), axis=1)

    elif 'career management' in module_name:
        concat_list = ['situation', 'new opportunity', 'small action']
        df['concat_answers'] = df.apply(lambda x: ' '.join(x[col] for col in df.columns if any(term in col.lower() for term in concat_list)), axis=1)

    return df
   

def add_quiz_answers(master_progress, course, gc):
    """
    Adds quiz answer data to a master progress DataFrame.
    
    This function takes a master progress DataFrame (master_progress), a course object (course), and a 
    Google Sheets client object (gc) as input. It uses the course object and the Google Sheets API to 
    retrieve quiz answer data for the specified course, and matches the quiz answer data with the email 
    addresses in the master progress DataFrame. The quiz answers are added to the master progress DataFrame 
    as new columns.
    
    Args:
    master_progress (pd.DataFrame): The master progress DataFrame to which quiz answer data will be added.
    course (Course): A course object containing the name and URL of the course being processed.
    gc (gspread.client.Client): A Google Sheets client object used to retrieve quiz answer data from the course.
    
    Returns:
    pd.DataFrame: The modified master progress DataFrame with quiz answer data added.
    """
    
    # Open quiz answers
    survey = gc.open_by_url(course.data_url)

    # Save all gsheet worksheets into a list to limit API calls and work locally
    # Retrieve module names for column labelling at later point
    module_names = [str(sheet.title).split(' - ', 1)[1] for sheet in survey.worksheets()]


    # change the order of module names to control the order in which they appear
    order_dict = {}

    for module in module_names:
        print(f'{module} answers retrieved.')

    # Create list of dataframes per answer sheet, then zip it with corresponding module name
    answers = [pd.DataFrame(sheet.get_all_records()) for sheet in survey.worksheets()]
    zipped_df = list(zip(module_names, answers))

    # Create blank dataframe to append each user entry with corresponding answers
    answers_master = pd.DataFrame()
    # For each user instance
    for index, row in master_progress.iterrows():
        # using email as primary key per user
        user_email = row['Email']
        # if user_email == 'snali@mun.ca':
        #     print('my man')
        # Create initial dataframe that only includes user's email for later merging
        user_answers = [pd.DataFrame([user_email], columns=['email'])]
        # For each survey worksheet
        for module_name, df in zipped_df:
            # Retrieve all instances from user - Skip answers with no email field
            try:
                answer_list = df.loc[df['email'] == user_email]
            except KeyError:
                continue

            # If user has multiple entries, take the latest one
            if answer_list.shape[0] > 1:
                submission_dates = answer_list['Submitted At'].to_list()
                # Limit answers down to latest submission by finding latest date then selecting corresponding row
                formatted_submission_dates = [datetime.strptime(date, '%m/%d/%Y %H:%M:%S') for date in submission_dates]
                latest_date = max(formatted_submission_dates).strftime("%-m/%-d/%Y %-H:%M:%S")
                #Convert datetime object back to string to match cell value and select latest row only

                ''' THIS IS CAUSING PROBLEMS BECAUSE ITS NOT MATCHING ANY ENTRIES - did i already fix this? Im pretty sure I did'''
                answer_list = answer_list.loc[answer_list['Submitted At'] == latest_date]

            elif answer_list.empty:
                continue
            
            # Apply a concat method to create a new field for reporting requirement to concat answers into one field
            answer_list = concat_answers(answer_list, module_name)


            # Add columns prefixes excluding 'email' column for merging
            answer_list.columns = [f'{module_name}_' + str(col) if str(col)!= 'email' else str(col) for col in answer_list.columns ]
            user_answers.append(answer_list)

        # merges list of dataframes per module to create one cohesive list of all module answers per single student email
        user_answers = reduce(lambda x, y: pd.merge(x, y, on='email') if not y.empty else x, user_answers)
        # Add user entry to master list
        answers_master = pd.concat([answers_master, user_answers], ignore_index=True)

    # rename email column to match master sheet column naming
    answers_master.rename(columns={'email': 'Email'}, inplace=True)

    master_progress = pd.merge(master_progress, answers_master, on='Email')
    
    return master_progress


def write_to_gs(gc, df, url, worksheet):
    """
    Writes a DataFrame to a Google Sheets worksheet.
    
    This function takes a Google Sheets client object (gc), a DataFrame (df), a Google Sheets URL (url), 
    and a worksheet name (worksheet) as input. It writes the DataFrame to the specified worksheet in the 
    specified Google Sheets document.
    
    Args:
    gc (gspread.client.Client): A Google Sheets client object used to write the DataFrame to the worksheet.
    df (pd.DataFrame): The DataFrame to be written to the worksheet.
    url (str): The URL of the Google Sheets document where the DataFrame will be written.
    worksheet (str): The name of the worksheet where the DataFrame will be written.
    """
    data = gc.open_by_url(url).worksheet(worksheet)
    data.clear()
    set_with_dataframe(worksheet=data, dataframe=df, include_index=False,
    include_column_header=True, resize=True)


def __parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no_emails', '-n',  help='Skip email download and use locally stored downloads', action='store_true')
    parser.add_argument('--exports', '-e',  help='Automate export retrieval', action='store_true')
    # ADD ARGUMENTS HERE
    args = parser.parse_args()

    return args


def __wait_time(wait_minutes):
    """
    Waits for the specified number of minutes.

    Args:
    wait_minutes (float): The number of minutes to wait.
    """
    wait_seconds = round(float(wait_minutes)*60)
    print(f'INITIATING WAIT TIME FOR {wait_seconds} SECONDS...')

    while wait_seconds:
        mins, secs = divmod(wait_seconds, 60)
        timer = '=== {:02d}:{:02d} ==='.format(mins, secs)
        print(timer, end="\r")
        sleep(1)
        wait_seconds -= 1


def final_formatting(master_progress):
    """
    Drops unwanted columns from the master progress DataFrame.

    Args:
    master_progress (pd.DataFrame): The master progress DataFrame.

    Returns:
    pd.DataFrame: The updated master progress DataFrame.
    """
    drop_list = ['Token', 'last_name', 'first_name']
    for term in drop_list:
        master_progress = master_progress[master_progress.columns.drop(list(master_progress.filter(regex=term)))]

    return master_progress


def add_credential_status(gc, master_progress, course):
    """
    Adds the credential status and notes to the master progress DataFrame.

    Args:
    gc (pygsheets.client.Client): The Google Sheets client.
    master_progress (pd.DataFrame): The master progress DataFrame.
    course (Course): The Course object.

    Returns:
    pd.DataFrame: The updated master progress DataFrame.
    """
    

    # master_progress['Credential Status'] = ''
    # master_progress['Notes'] = ''
    df = pd.DataFrame(gc.open_by_url(course.credential_url).worksheet('Sheet1').get_all_records())
    if df.empty:
        return master_progress

    df = df[['Email', 'Credential Status', 'Notes']]
    master_progress = master_progress.merge(df, on='Email', how='left', suffixes=['', '_y'])
    # for index, row in df.iterrows():
    #     master_progress.loc[master_progress['Email'] == row['Email']]['Credential Status'] = row['Credential Status']
    #     master_progress.loc[master_progress['Email'] == row['Email']]['Notes'] = row['Notes']

    return master_progress


def __gdrive_authenticate():
    """
    Authenticates with Google Drive and returns the authenticated client.

    Returns:
        GoogleDrive: The authenticated GoogleDrive client.
    """
        
    gauth = GoogleAuth()
    # Try to load saved client credentials
    gauth.LoadCredentialsFile("client_secrets.json")
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("client_secrets.json")
    drive = GoogleDrive(gauth)

    return drive


def write_group_reports(partner_df, master_progress, course):
    """
    Writes progress reports for each group to their corresponding Google Drive folder.

    Args:
        partner_df (pd.DataFrame): The partner DataFrame.
        master_progress (pd.DataFrame): The master progress DataFrame.
        course (Course): The Course object.
    """
    drive = __gdrive_authenticate()

    for _, row in partner_df.iterrows():
        group = row['Group']
        folder_url = row[course.name]
        folder_id = folder_url.lstrip('https://drive.google.com/drive/folders/')
        file_name = f'{group} Progress Report.csv'
        df = master_progress.loc[master_progress['Group'] == group.lower().title()]     
        df.to_csv(os.path.join(course.name, 'Reports', file_name), index=None)
        try:
            file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()
        
            for file in file_list:
                if file_name == file['title']:
                    file.Trash()
        except:
            pass
        
        gfile = drive.CreateFile({'title': f'{file_name}', 'parents': [{'id': folder_id}]})
       
        gfile.SetContentFile(os.path.join(course.name, 'Reports', file_name))
        gfile.Upload() # Upload the file.
    
    
def extended_survey_flag(master_progress):
    master_progress['Extended Survey Eligibility'] = ''
    for index, row in master_progress.iterrows():
        test1 = row['Before You Begin + Welcome Survey_Which best describes you?  Are you currently..._1']
        test2 = row["Before You Begin + Welcome Survey_Which best describes you? Are you currently..._2"]
        test3 = row['Before You Begin + Welcome Survey_The Tech Stewardship Practice Program is most effective when it overlays a current experiential or work integrated learning experience. Please let us know what type of experience opportunity(s) you will have this semester:']

        if (test1 in ["Completing a Bachelor's degree",'Completing an apprenticeship or trades qualification', 'Completing a College/CEGEP certificate or diploma', 'Completing a University certificate or diploma'] and
            test2 in ["A Canadian citizen studying at a Canadian post-secondary institution", "A Canadian permanent resident studying at a Canadian post-secondary institution", "An international student studying at a Canadian post-secondary institution"] and
            test3 in ['I will not have a current experiential or work integrated learning experience this semester']):
            master_progress.loc[index, 'Extended Survey Eligibility'] = 'Yes'
    return master_progress
    

def print_intro():
    print('\n=================================================================================\n')
    print(pyfiglet.figlet_format('TECH  STEWARDSHIP', font='small', justify='center'))
    print(pyfiglet.figlet_format('REPORTING', font='small', justify='center'), '\n')

    print('Written by:\n'+ pyfiglet.figlet_format('   Dylan  Doyle', font='smslant'))
    print('Last Updated: Apr 29, 2023')
    print('=================================================================================')


def reorder_columns(df):
    """
    Reorders the columns in the given DataFrame based on a predefined order.
    The function first reorders the DataFrame based on the col_list, then appends
    the '_concat_answers' columns along with their corresponding 'thank you for sharing'
    columns if they exist, and finally appends any remaining columns.

    :param df: DataFrame to be reordered
    :return: Reordered DataFrame with columns arranged in the desired order
    """

    # predefined column order
    col_list = ['First Name', 'Last Name', 'Email', 'Credential Status', 'Notes', 'Last Sign In', 'Request a micro-credential_Submitted At', 'Group', 'Company' 'Attendance Count', '% Completed']

    # Extract all 'concat_answers' columns to be reordered earlier in the df and include 'thank you for sharing' entry if exists
    concat_list = []
    for col in df.columns:
        # Check if the column name contains '_concat_answers'
        if '_concat_answers' in col:
            concat_list.append(col)

            module_name = col.split('_concat_answers')[0]
            # Search for the 'thank you for sharing' column with the same module name
            sharing_col = [c for c in df.columns if f'{module_name}_Thank' in c]
            # If a matching column is found, add it to the concat_list
            if sharing_col:
                concat_list.append(sharing_col[0])


    third_col_list = ['Feedback_Overall how do you rate your experience of participating in the TS program?']


    df = df[col_list + concat_list + third_col_list + [col for col in df.columns if col not in col_list + concat_list]]
    return df


def main():
    print_intro()
    username, password, ts_password = LOGIN_DICT['user'], LOGIN_DICT['pass'], LOGIN_DICT['ts_pass']
    # Create arg parser instance
    args = __parser()

    # Create Google cloud authentication instance
    gc = gspread_authenticate()

    # Create Thinkific login object to query API
    thinkific = Thinkific(LOGIN_DICT['api_key'], 'marsdd')

    print('\n=====================')
    print('Creating courses...')
    print('=====================')

    course = create_course(COURSE_CONFIG_URL, thinkific, gc)
    partner_df, participant_group_list = get_reporting_groups(gc, course)
    

    # Export dialog enabled
    if args.exports is True:
        wait_minutes = input('Enter wait time in minutes:\n')
        get_exports(participant_group_list, course, username, ts_password)
        __wait_time(wait_minutes)
        print('\n=====================')

    # Create course folders
    Path(os.path.join(course.name, 'Reports')).mkdir(parents=True, exist_ok=True)
    Path(os.path.join(course.name, 'Downloaded Reports')).mkdir(parents=True, exist_ok=True)

    # Report download via email
    if args.no_emails is False:
        print('\n=====================')
        files = get_email_link(username, password, course)
        get_downloads(files, username, ts_password, course.name)
        print('=====================\n')

    print('\n=====================')
    print('Creating groups...')
    print('=====================\n')
    groups = create_groups(course)
    print('Completed.\n')
    print('\n=====================')
    print('Generating progress reports...')
    print('=====================\n')

    master_progress = generate_prog_reports(course, groups)
    write_to_gs(gc, master_progress, course.thinkific_url, 'Sheet1')
    print('Completed.\n')
    print('\n=====================')
    print('Adding attendance...')
    print('=====================\n')
    master_progress = add_attendance(master_progress, course, gc)
    print('Completed.\n')
    print('\n=====================')
    print('Adding survey answers...')
    print('=====================\n')
    master_progress = add_quiz_answers(master_progress, course, gc)

    # This extended survey is a tad hard coded, isn't currently working for fall
    if 'Fall 2022' not in course.name:
        master_progress = extended_survey_flag(master_progress)

    print('Completed.\n')
    print('\n=====================')
    print('Building Partner Reports...')
    print('=====================\n')
    
    # should i put this loweR?
    master_progress.drop_duplicates(inplace=True)
    
    master_progress = final_formatting(master_progress)
    master_progress = add_credential_status(gc, master_progress, course)
    master_progress = reorder_columns(master_progress)
    master_progress.sort_values(by='Email', inplace=True)
    write_group_reports(partner_df, master_progress, course)

    print('Completed.\n')
    
##----------------- FINAL UPLOAD ----------------------##


    print('\n=====================')
    print('Writing to Master File...')
    print('=====================\n')
    master_progress.to_csv("Master.csv", index=None)
    write_to_gs(gc, master_progress, course.master_url, 'Sheet1')
    print('Completed, EXITING...\n')

if __name__ == '__main__':
    main()
