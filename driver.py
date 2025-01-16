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


class Bot:
    """
    Bot class that automates WhatsApp Web interactions using a Chrome driver.
    """

    def __init__(self, session_name=None):
        # Configure Chrome options
        options = Options()

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

            except Exception as e:
                page_load = True
                print(f"Error during login: {e}")
                print("Retrying login...")

            # Wait before retrying to prevent an infinite loop from flooding the system
            time.sleep(5)

        # Record the start time for logs once the login is successful
        self._start_time = time.strftime("%d-%m-%Y_%H%M%S", time.localtime())
        self.send_messages_to_all_contacts()

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

    def generate_chat_history_csv(self):
        """
        Generates CSV files from chat history
        """
        self.check_login()
        sleep(3)  # Wait for page to load

        # Try first with 'Chat list'
        chat_items = self.driver.find_elements(
            By.XPATH, "//div[@aria-label='Chat list']//div[@role='listitem']")

        # If no results, try with 'Lista de conversas'
        if not chat_items:
            chat_items = self.driver.find_elements(
                By.XPATH, "//div[@aria-label='Lista de conversas']//div[@role='listitem']")

        print(f"Found {len(chat_items)} chats")

        # For testing, only process first chat
        chat_items = [chat_items[0]]

        for chat in chat_items:
            try:
                # Get chat name
                name = chat.find_element(By.XPATH, ".//span[@dir='auto']").text
                print(f"Processing chat: {name}")

                # Click on chat
                chat.click()
                sleep(2)

                # Get messages
                messages = self.get_all_messages()

                # Convert messages to DataFrame
                df = self.messages_to_dataframe(messages)

                # Save to CSV
                csv_filename = f"{name}_chat_history.csv"
                df.to_csv(csv_filename, index=False, encoding='utf-8')
                print(f"Saved chat history to {csv_filename}")

            except Exception as e:
                print(f"Error processing chat {name}: {e}")

        print(Fore.GREEN + "CSV generation complete!" + Style.RESET_ALL)

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

    def get_messages(conversation_container):
        """
        Gets current visible messages from conversation container
        """
        return conversation_container.find_elements(
            By.CSS_SELECTOR, ".message-in, .message-out")

    def scroll_chat(self, conversation_container):
        """
        Scrolls chat up and waits for content to load
        """
        self.driver.execute_script(
            "arguments[0].scrollTop = 0;", conversation_container)
        sleep(2)

    def load_history(self):
        """
        Checks and clicks older messages button if present
        Retries on StaleElementReferenceException
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                older_messages_button = self.driver.find_elements(
                    By.CLASS_NAME, "x14m1o6m")

                if older_messages_button:  # If list is not empty
                    older_messages_button[0].click()
                    sleep(10)
                    return True
                return False

            except StaleElementReferenceException:
                print(
                    f"Stale element, retrying... (attempt {attempt + 1}/{max_retries})")
                sleep(3)
                continue

        return False  # Return False if all retries failed

    def get_all_messages(self):
        """
        Gets all messages from current chat by scrolling up and loading history
        """
        conversation_container = self.driver.find_element(
            By.XPATH, '//*[@id="main"]/div[3]/div/div[2]')

        # First, scroll to the top of history
        while True:
            # Try to load older messages if button is present
            self.load_history()

            # Scroll up
            self.scroll_chat(conversation_container)
            sleep(2)

            # Get current scroll height
            current_height = self.driver.execute_script(
                "return arguments[0].scrollHeight", conversation_container)

            # Break only if no older messages button is found
            older_messages_button = self.driver.find_elements(
                By.CLASS_NAME, "x14m1o6m")
            if older_messages_button == []:
                print("Nao encontrou nada")
                break

        # Now get all messages
        messages_elements = self.get_messages(conversation_container)
        return self.get_all_message_info(messages_elements)

    def decode_latin(self, text):
        """
        Decodes text from various encodings
        """
        try:
            # First attempt: decode directly as utf-8
            return text.encode().decode('utf-8')
        except Exception as e1:
            try:
                # Second attempt: decode unicode characters
                return bytes(text, 'utf-8').decode('unicode_escape')
            except Exception as e2:
                try:
                    # Third attempt: modified original method
                    return text.encode('raw_unicode_escape').decode('utf-8')
                except Exception as e3:
                    print(f"Warning: Could not decode text: '{text}'")
                    print(f"Errors: {e1}, {e2}, {e3}")
                    return text

    def get_all_message_info(self, messages_elements):
        """
        Extracts information from message elements
        """
        messages = []
        for message in messages_elements:
            try:
                copyable_text = message.find_elements(
                    By.CSS_SELECTOR, ".copyable-text")
                time, date, sender, utc_dt = None, None, None, None

                # Check for quoted message
                quoted_message = None
                quoted_elements = message.find_elements(
                    By.CSS_SELECTOR, "div[role='button'][aria-label='Quoted message']")
                if len(quoted_elements) > 0:
                    try:
                        quoted_sender = quoted_elements[0].find_elements(
                            By.CSS_SELECTOR, "span[dir='auto']._ao3e")
                        quoted_text = quoted_elements[0].find_elements(
                            By.CSS_SELECTOR, "span.quoted-mention._ao3e")
                        if len(quoted_text) > 0:
                            quoted_message = {
                                "sender": quoted_sender[0].text if len(quoted_sender) > 0 else '',
                                "text": quoted_text[0].text
                            }
                    except Exception as e:
                        print(f"Error processing quoted message: {e}")

                text = ''
                if len(copyable_text) > 0:
                    main_text_element = message.find_elements(
                        By.CSS_SELECTOR, "span.selectable-text.copyable-text")
                    if len(main_text_element) > 0:
                        try:
                            text = self.decode_latin(
                                main_text_element[0].text.strip())
                        except Exception as e:
                            print(f"Error processing main message: {e}")

                    date_text = copyable_text[0].get_attribute(
                        "data-pre-plain-text")
                    if date_text:
                        # Extract date from format '[HH:MM, DD/MM/YYYY] Name: '
                        date_parts = date_text.split('] ')[
                            0].replace('[', '').split(', ')
                        time = date_parts[0]
                        date = date_parts[1]
                        sender = date_text.split('] ')[1].replace(': ', '')

                        # Convert to UTC
                        # Assuming São Paulo timezone
                        local_tz = pytz.timezone('America/Sao_Paulo')
                        datetime_str = f"{date} {time}"
                        local_dt = datetime.strptime(
                            datetime_str, "%d/%m/%Y %H:%M")
                        local_dt = local_tz.localize(local_dt)
                        utc_dt = local_dt.astimezone(pytz.UTC)

                attachment_data = None
                # Check for images
                image_elements = message.find_elements(
                    By.CSS_SELECTOR, "img[data-testid='image-thumb'], img[class*='x15kfjtz']")
                if len(image_elements) > 0:
                    attachment_data = self.process_image_attachment(
                        image_elements[0])

                # Check for PDFs
                pdf_elements = message.find_elements(
                    By.CSS_SELECTOR, "div[role='button'][title^='Download']")
                if pdf_elements:
                    try:
                        file_name = pdf_elements[0].find_element(
                            By.CSS_SELECTOR, "span.x13faqbe._ao3e").text
                        file_size = pdf_elements[0].find_element(
                            By.CSS_SELECTOR, "span[title$='kB']").text

                        attachment_data = {
                            "type": "document",
                            "name": file_name,
                            "size": file_size,
                            "file_type": "PDF" if file_name.lower().endswith('.pdf') else "unknown",
                            "content": None
                        }
                    except Exception as e:
                        print(f"Error processing PDF details: {e}")
                        attachment_data = {
                            "type": "document",
                            "name": file_name if 'file_name' in locals() else "Unknown"
                        }

                # Check for audio messages
                audio_elements = message.find_elements(
                    By.CSS_SELECTOR, "audio[data-testid='audio-player']")
                if audio_elements:
                    try:
                        download_button = message.find_element(
                            By.CSS_SELECTOR, "button[aria-label='Download voice message']")
                        download_button.click()
                        sleep(2)

                        duration = message.find_element(
                            By.CSS_SELECTOR, "div._ak8w").text

                        max_wait = 30
                        start_time = datetime.now()
                        downloaded_file = None

                        while (datetime.now() - start_time).total_seconds() < max_wait:
                            files = os.listdir(self.TEMP_DIR)
                            audio_files = [f for f in files if f.endswith(
                                ('.mp3', '.ogg', '.m4a'))]
                            if audio_files:
                                downloaded_file = os.path.join(
                                    self.TEMP_DIR, audio_files[0])
                                break
                            sleep(1)

                        if downloaded_file:
                            attachment_data = {
                                "type": "audio",
                                "duration": duration,
                                "file_path": downloaded_file,
                            }
                        else:
                            print("Timeout: Audio file not downloaded")
                            attachment_data = {
                                "type": "audio",
                                "duration": duration,
                                "error": "Download failed"
                            }

                    except Exception as e:
                        print(f"Error processing audio message: {e}")
                        attachment_data = {
                            "type": "audio",
                            "error": str(e)
                        }

                message_data = {
                    "text": text,
                    "time": time,
                    "date": date,
                    "sender": sender,
                    "quoted_message": quoted_message,
                    "attachment_data": attachment_data,
                    "timestamp_utc": utc_dt.isoformat() if utc_dt else None,
                }

                messages.append(message_data)
            except Exception as e:
                print(f"Error processing a message: {e}")
        return messages

    def process_image_attachment(self, image_element):
        """
        Processes image attachments
        """
        try:
            return {
                "type": "image",
                "src": image_element.get_attribute("src"),
                "alt": image_element.get_attribute("alt")
            }
        except Exception as e:
            print(f"Error processing image attachment: {e}")
            return {
                "type": "image",
                "error": str(e)
            }
