import csv
import os.path
import random
import time
from time import sleep

from colorama import Fore, Style
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from undetected_chromedriver import Chrome
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException


import json
import pandas as pd
from datetime import datetime
import pytz
from database import MessageDatabase

# Define a timeout for waiting for elements to load
timeout = 30


class Contact:
    def __init__(self, name, number, db):
        self.db = db
        contact = self.db.get_contact_by_number(number)
        messages = self.db.get_all_chat_history_by_number(number)
        if contact:
            self.number = contact[0]
            self.name = contact[1]
            self.created_at = datetime.fromisoformat(
                contact[2]) if contact[2] else None
            self.updated_at = datetime.fromisoformat(
                contact[3]) if contact[3] else None
            self.last_message = contact[4]
            self.last_message_timestamp = datetime.fromisoformat(
                contact[5]) if contact[5] else None
            self.first_message_found = contact[6]
            self.first_message_found_timestamp = datetime.fromisoformat(
                contact[7]) if contact[7] else None
            self.is_first_message = bool(contact[8])
            self.received_receipt = bool(contact[9])
            self.received_receipt_timestamp = datetime.fromisoformat(
                contact[10]) if contact[10] else None
            self.is_ws_business = bool(contact[11])
            self.try_to_get_messages_error = bool(contact[12])
            self.is_complete = bool(contact[13])
            self.messages = messages
        else:
            self.number = number
            self.name = name
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
            self.last_message = None
            self.last_message_timestamp = None
            self.first_message_found = None
            self.first_message_found_timestamp = None
            self.is_first_message = False
            self.received_receipt = False
            self.received_receipt_timestamp = None
            self.is_ws_business = False
            self.try_to_get_messages_error = False
            self.is_complete = False
            self.messages = []
            self.db.save_contact(self.number, self.name,  self.last_message, self.last_message_timestamp,
                                 self.first_message_found, self.first_message_found_timestamp,
                                 self.is_first_message, self.received_receipt, self.received_receipt_timestamp,
                                 self.try_to_get_messages_error, self.is_complete)

    def __str__(self):
        return f"{self.name} | {self.number}"

    def update_last_message(self, message, timestamp):
        """Update last message and timestamp"""
        self.last_message = message
        # Converter timestamp para datetime se for string
        if isinstance(timestamp, str):
            self.last_message_timestamp = datetime.fromisoformat(timestamp)
        else:
            self.last_message_timestamp = timestamp

        return self.db.save_contact(
            self.number,
            self.name,
            self.last_message,
            self.last_message_timestamp,
            self.first_message_found,
            self.first_message_found_timestamp,
            self.is_first_message,
            self.received_receipt,
            self.received_receipt_timestamp,
            self.try_to_get_messages_error,
            self.is_complete
        )

    def update_first_message(self, message, timestamp_str, is_first_message=False):
        """Update first message found"""
        self.first_message_found = message
        # Converter timestamp para datetime se for string
        if isinstance(timestamp_str, str):
            self.first_message_found_timestamp = datetime.fromisoformat(
                timestamp_str)
        else:
            self.first_message_found_timestamp = timestamp_str
        self.is_first_message = is_first_message

        return self.db.save_contact(
            self.number,
            self.name,
            self.last_message,
            self.last_message_timestamp,
            self.first_message_found,
            self.first_message_found_timestamp,
            self.is_first_message,
            self.received_receipt,
            self.received_receipt_timestamp,
            self.try_to_get_messages_error,
            self.is_complete
        )

    def update_received_receipt(self, timestamp):
        """Update received receipt status and timestamp"""
        self.received_receipt = True
        # Converter timestamp para datetime se for string
        if isinstance(timestamp, str):
            self.received_receipt_timestamp = datetime.fromisoformat(timestamp)
        else:
            self.received_receipt_timestamp = timestamp

        return self.db.save_contact(
            self.number,
            self.name,
            self.last_message,
            self.last_message_timestamp,
            self.first_message_found,
            self.first_message_found_timestamp,
            self.is_first_message,
            self.received_receipt,
            self.received_receipt_timestamp,
            self.try_to_get_messages_error,
            self.is_complete
        )

    def update_is_complete(self, is_complete):
        self.is_complete = is_complete
        self.db.save_contact(self.number, self.name, self.last_message, self.last_message_timestamp,
                             self.first_message_found, self.first_message_found_timestamp, self.is_first_message,
                             self.received_receipt, self.received_receipt_timestamp, self.try_to_get_messages_error,
                             self.is_complete)

    def update_is_first_message(self, is_first_message):
        self.is_first_message = is_first_message
        self.db.save_contact(self.number, self.name, self.last_message, self.last_message_timestamp,
                             self.first_message_found, self.first_message_found_timestamp, self.is_first_message,
                             self.received_receipt, self.received_receipt_timestamp, self.try_to_get_messages_error,
                             self.is_complete)


class Bot:
    """
    Bot class that automates WhatsApp Web interactions using a Chrome driver.
    """

    def __init__(self, session_name=None):
        # Configure Chrome options
        options = Options()

        # Mute audio
        options.add_argument("--mute-audio")

        # Use provided session name or default
        chrome_data_dir = os.path.join(os.getcwd(), 'chrome-data')
        session_path = os.path.join(
            chrome_data_dir, session_name if session_name else 'default')
        options.add_argument(f"--user-data-dir={session_path}")

        # TODO mudar para DOWNLOAD_DIR
        self.TEMP_DIR = os.path.join(os.getcwd(), 'Downloads')
        options.add_argument(f"--download.default_directory={self.TEMP_DIR}")
        options.add_argument("--download.prompt_for_download=false")
        options.add_argument("--download.directory_upgrade=true")
        options.add_argument("--safebrowsing.enabled=true")
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        self.driver = Chrome(service=ChromeService(
            ChromeDriverManager().install()), options=options)

        # Configure download settings using CDP
        self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': self.TEMP_DIR
        })

        self._message = None
        self._csv_numbers = None
        self._options = [False, False]  # [include_names, include_media]
        self._start_time = None
        self.__prefix = None
        self._first_time_login = False
        # Selector may change in time
        self.__main_selector = "//p[@dir='ltr']"
        self.__fallback_selector = "//div[@class='x1hx0egp x6ikm8r x1odjw0f x1k6rcq7 x6prxxf']//p[@class='selectable-text copyable-text x15bjb6t x1n2onr6']"
        self.__media_selector = "//div[@class='x1hx0egp x6ikm8r x1odjw0f x1k6rcq7 x1lkfr7t']//p[@class='selectable-text copyable-text x15bjb6t x1n2onr6']"

        self.db = MessageDatabase()

    def click_button(self, css_selector):
        """
        Clicks the send button (specified by its CSS selector).
        """
        button = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
        )
        sleep(1)
        button.click()

    def construct_whatsapp_url(self, number):
        """
        Constructs the WhatsApp Web URL for opening a chat with a contact.
        """
        return f'https://web.whatsapp.com/send?phone={self.__prefix}{number.strip()}&type=phone_number&app_absent=0'

    def login(self, prefix):
        """
        Logs in to WhatsApp Web by navigating to the login page.
        Waits indefinitely until the QR code is scanned and/or clickable element appears.
        Prompts the user every few seconds to scan the QR code if not already logged in.
        """
        self.__prefix = prefix
        logged_in = False  # Track login status
        page_load = False  # Track page load status

        while not logged_in:  # Loop only until login is successful
            try:
                if not page_load:
                    self.driver.get('https://web.whatsapp.com')
                print("Attempting to load WhatsApp Web...")

                # Wait for the clickable element, success_message and error_message are shown only once
                logged_in = self.wait_for_element_to_be_clickable(
                    "//div[@class='x1n2onr6 x14yjl9h xudhj91 x18nykt9 xww2gxu']",
                    success_message="Logged in successfully!",
                    error_message="Waiting for QR code to be scanned..."
                )
                if logged_in:
                    break  # Exit the loop on successful login
                else:
                    self._first_time_login = True

            except Exception as e:
                page_load = True
                print(f"Error during login: {e}")
                print("Retrying login...")

            # Wait before retrying to prevent an infinite loop from flooding the system
            time.sleep(5)

        # Record the start time for logs once the login is successful
        self._start_time = time.strftime("%d-%m-%Y_%H%M%S", time.localtime())

    def log_result(self, number, error):
        """
        Logs the result of each message send attempt.
        """
        assert self._start_time is not None
        log_path = "logs/" + self._start_time + \
            ("_notsent.txt" if error else "_sent.txt")

        with open(log_path, "a") as logfile:
            logfile.write(number.strip() + "\n")

    def prepare_message(self, name):
        """
        Prepares the message, including the recipient's name if specified.
        """
        if self._options[0] and name:
            return self._message.replace("%NAME%", name)
        return self._message.replace("%NAME%", "")

    def quit_driver(self):
        """
        Closes the WebDriver session and quits the browser.
        """
        if self.driver:
            self.driver.quit()
            print(Fore.YELLOW, "Driver closed successfully.", Style.RESET_ALL)

    def type_message(self, text_element, message):
        """
        Types the message into the appropriate text element.
        Handles multiline messages.
        """
        multiline = "\n" in message
        if multiline:
            for line in message.split("\n"):
                text_element.send_keys(line)
                text_element.send_keys(Keys.LEFT_SHIFT + Keys.RETURN)
        else:
            text_element.send_keys(message)

    def send_message_to_contact(self, url, message):
        """
        Sends a message or media via WhatsApp Web by interacting with the webpage elements.
        """
        try:
            self.driver.get(url)

            # Try to click the main input box, if it fails, try the fallback
            try:
                message_box = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, self.__main_selector))
                )

            except:
                message_box = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, self.__fallback_selector))
                )

            # If media is included proceed differently
            if self._options[1]:
                message_box.send_keys(Keys.CONTROL, 'v')
                sleep(random.uniform(2, 5))  # Allow time for media to paste
                message_box = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, self.__media_selector))
                )

            # Type and send the message
            self.type_message(message_box, message)

            # Click the send button
            self.click_button("span[data-icon='send']")

            sleep(random.uniform(2, 5))  # Delay before moving on
            print(
                Fore.GREEN + "Message and media (if any) sent successfully." + Style.RESET_ALL)
            return False  # No error

        except Exception as e:
            print(e)
            print(Fore.RED + "Error sending message and media." + Style.RESET_ALL)
            return True  # Error occurred

    def send_messages_to_all_contacts(self):
        """
        Sends messages to all contacts listed in the provided CSV file.
        Closes the driver after execution.
        """
        if not os.path.isfile(self._csv_numbers):
            print(Fore.RED, "CSV file not found!", Style.RESET_ALL)
            return

        try:
            with open(self._csv_numbers, mode="r") as file:
                csv_reader = csv.reader(file)
                multiline = "\n" in self._message

                for row in csv_reader:
                    name, number = row[0], row[1]
                    print(f"Sending message to: {name} | {number}")
                    message = self.prepare_message(name)
                    url = self.construct_whatsapp_url(number)

                    error = self.send_message_to_contact(url, message)
                    self.log_result(number, error)

                    # Save successful messages to database
                    if not error:
                        self.db.save_sent_message(number, name, message)

                    # Random sleep between sending messages to avoid being detected
                    sleep(random.uniform(1, 10))
        finally:
            self.db.close()  # Close database connection
            self.quit_driver()

    def wait_for_element_to_be_clickable(self, xpath, success_message=None, error_message=None, timeout=timeout):
        """
        Waits for an element to be clickable within the specified timeout period.
        :param xpath: The XPATH of the element to wait for.
        :param success_message: Message to display when the element becomes clickable.
        :param error_message: Message to display in case of timeout.
        :param timeout: Time (in seconds) to wait for the element to become clickable.
        :return: True if the element becomes clickable, False otherwise.
        """
        try:
            # Wait for the element to become clickable
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            if success_message:
                print(Fore.GREEN + success_message + Style.RESET_ALL)
            return True  # Element is clickable, return True

        except TimeoutException:
            if error_message:
                print(Fore.RED + error_message + Style.RESET_ALL)
            return False  # Timeout occurred, return False

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, txt_file):
        with open(txt_file, "r") as file:
            self._message = file.read()

    @property
    def csv_numbers(self):
        return self._csv_numbers

    @csv_numbers.setter
    def csv_numbers(self, csv_file):
        self._csv_numbers = csv_file

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, opt):
        self._options = opt

    def count_chats(self):
        """
        Counts and returns the number of chat elements on WhatsApp Web.
        """
        try:
            # Wait for chat elements to load
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "x10l6tqk"))
            )

            # Find all chat elements
            chat_elements = self.driver.find_elements(
                By.CLASS_NAME, "x10l6tqk")
            chat_count = len(chat_elements)

            print(Fore.CYAN +
                  f"\nNumber of chats found: {chat_count}" + Style.RESET_ALL)
            return chat_count

        except Exception as e:
            print(Fore.RED + f"Error counting chats: {e}" + Style.RESET_ALL)
            return 0

    def check_login(self):
        """
        Checks if the user is logged in to WhatsApp Web, if not, logs in.
        """
        current_url = self.driver.current_url
        if "https://web.whatsapp.com/" not in current_url:
            self.login()
            sleep(3)
        else:
            print(Fore.GREEN + "Already logged in!" + Style.RESET_ALL)

    def login_and_count_chats(self):
        """
        Logs into WhatsApp Web and counts the number of chats.
        """
        try:
            self.driver.get('https://web.whatsapp.com')
            print("Attempting to load WhatsApp Web...")

            logged_in = False
            while not logged_in:
                logged_in = self.wait_for_element_to_be_clickable(
                    "//div[@class='x1n2onr6 x14yjl9h xudhj91 x18nykt9 xww2gxu']",
                    success_message="Logged in successfully!",
                    error_message="Waiting for QR code to be scanned..."
                )

                if logged_in:
                    sleep(3)  # Small delay to ensure chats are loaded
                    self.count_chats()
                    break

                sleep(5)  # Wait before retrying

        except Exception as e:
            print(Fore.RED + f"Error during login: {e}" + Style.RESET_ALL)

    def click_first_chat_and_scroll(self):
        """
        Clicks on the first chat in the list and scrolls up in the chat history.
        """
        self.check_login()
        sleep(3)  # Add extra wait for page to fully load

        # Encontrar a lista de conversas
        chat_list_xpath = "//div[@aria-label='Chat list']//div[@role='listitem']"
        chat_items = self.driver.find_elements(By.XPATH, chat_list_xpath)

        # Extrair dados de cada chat
        all_chats = []
        for chat in chat_items:
            try:
                name = chat.find_element(By.XPATH, ".//span[@dir='auto']").text
                last_message = chat.find_element(
                    By.XPATH, ".//div[@role='gridcell']/span").text
                timestamp = chat.find_element(
                    By.XPATH, ".//div[@role='gridcell'][2]").text

                all_chats.append(f"{name} | {timestamp} | {last_message}")
            except Exception as e:
                print(f"Erro ao processar um chat: {e}")

    # TODO test
    def generate_chat_history_csv(self):
        """
        Generates CSV files from chat_history sql table
        """
        csv_path = self.db.csv_from_chat_history()
        if csv_path:
            print(Fore.GREEN + "CSV generation complete!" + Style.RESET_ALL)
        else:
            print(Fore.RED + "Error generating CSV file." + Style.RESET_ALL)

    def messages_to_dataframe(self, messages):
        """
        Converts message list to pandas DataFrame
        """
        # Extract relevant fields
        processed_messages = []

        for msg in messages:
            message_dict = {
                'sender': msg.get('sender'),
                'text': msg.get('text'),
                'date': msg.get('date'),
                'time': msg.get('time'),
                'timestamp_utc': msg.get('timestamp_utc'),
            }

            # Handle attachments
            if msg.get('attachment_data'):
                message_dict['attachment_type'] = msg['attachment_data'].get(
                    'type')
                message_dict['attachment_name'] = msg['attachment_data'].get(
                    'name')

            # Handle quoted messages
            if msg.get('quoted_message'):
                message_dict['quoted_sender'] = msg['quoted_message'].get(
                    'sender')
                message_dict['quoted_text'] = msg['quoted_message'].get('text')

            processed_messages.append(message_dict)

        return pd.DataFrame(processed_messages)
