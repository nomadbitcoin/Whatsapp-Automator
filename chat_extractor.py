import random
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from time import sleep
from datetime import datetime, timedelta
import pytz
import json
import os
from PIL import Image
import io
import pytesseract
import re
from faster_whisper import WhisperModel
import base64
from pydub import AudioSegment
from driver import Contact
from utils import decode_latin, convert_to_utc, is_receipt_by_keywords
from config import GROUP_ANALYZE, TEMP_DIR, OUTPUT_DIR, RECEIPT_KEYWORDS
import urllib.request
from browser_handler import retry_on_connection_error
from selenium.common.exceptions import StaleElementReferenceException


class ChatExtractor:
    def __init__(self, bot):
        self.bot = bot
        self.setup_tesseract()
        self.temp_dir = TEMP_DIR
        self.output_dir = OUTPUT_DIR

    def setup_tesseract(self):
        """Configure Tesseract to use local language files in the venv"""
        venv_path = os.environ.get('VIRTUAL_ENV', '.venv')
        tessdata_path = os.path.join(venv_path, 'tessdata')
        os.makedirs(tessdata_path, exist_ok=True)

        # Download Portuguese language data if needed
        por_traineddata = os.path.join(tessdata_path, 'por.traineddata')
        if not os.path.exists(por_traineddata):
            print("Downloading Portuguese language data...")
            url = "https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata"
            urllib.request.urlretrieve(url, por_traineddata)

        os.environ['TESSDATA_PREFIX'] = tessdata_path

    def extract_contact_number(self):
        '''Extract contact number from profile details'''
        # Click on Profile details
        profile_details = self.bot.driver.find_elements(
            By.XPATH, "//div[@title='Profile details']")
        if len(profile_details) > 0:
            profile_details[0].click()
            sleep(2)
        else:
            print(f'profile_details not found')
            return None

        # Check if the chat is a group
        group_text = self.bot.driver.find_elements(
            By.XPATH,
            "//section[contains(@class, 'x2lah0s')]//span[contains(text(), 'Group')]"
        )
        if len(group_text) > 0:
            if GROUP_ANALYZE:
                # Do something
                print(f'group_text: {group_text[0].text}')
            else:
                print(f'not analize group')
                # sair do loop for e pular para o proximo chat
                return

        phone_number = None
        # Check if the chat is a business
        business_text = self.bot.driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'x1iyjqo2') and contains(text(), 'This is a business account')]"
        )
        if len(business_text) > 0:
            phone_element = self.bot.driver.find_elements(
                By.XPATH,
                "//div[@class='xkhd6sd  _ajxt']"
            )

        else:
            print(f'not business')
            phone_element = self.bot.driver.find_elements(
                By.XPATH,
                "//section[contains(@class, 'x2lah0s')]//span[@class='x1jchvi3 x1fcty0u x40yjcy']"
            )

        if len(phone_element) > 0:
            phone_number = phone_element[0].text
            print(f'phone_number: {phone_number}')

        # close profile details
        close_button = self.bot.driver.find_elements(
            By.XPATH,
            "//span[@data-icon='x']"
        )
        if len(close_button) > 0:
            close_button[0].click()
            sleep(2)
        else:
            print(f'close_button not found')
        return phone_number

    @retry_on_connection_error(max_retries=3)
    def extract_all_chats(self):
        """Extract messages from all chats"""
        all_chats = set()

        while True:
            chat_items = self.bot.driver.find_elements(
                By.XPATH,
                "//div[@aria-label='Lista de conversas']//div[@role='listitem']"
            )

            if not chat_items:
                chat_items = self.bot.driver.find_elements(
                    By.XPATH,
                    "//div[@aria-label='Chat list']//div[@role='listitem']"
                )

            already_collected_chats = []
            for chat in chat_items:
                try:
                    name = chat.find_element(
                        By.XPATH,
                        ".//span[@dir='auto']"
                    ).text

                    if name not in all_chats:
                        all_chats.add(name)
                        self._current_chat_name = name
                        chat.click()
                        sleep(2)
                        # Init Contact
                        number = self.extract_contact_number()
                        if not number:
                            print(f'No number found for {name}, skipping...')
                            continue

                        contact = Contact(name, number, self.bot.db)

                        messages = self.get_all_messages(contact)

                        self._save_messages_to_file(name, messages)
                        chat.click()
                        sleep(2)
                        self._current_chat_name = None
                    else:
                        already_collected_chats.append(name)
                except Exception as e:
                    print(f"Error processing chat: {e}")
                    self._current_chat_name = None

            if len(already_collected_chats) == len(chat_items):
                break

            self._scroll_chats_list()

        return all_chats

    def get_all_messages(self, contact: Contact):
        """Extract all messages from current chat"""
        conversation_container = self.bot.driver.find_element(
            By.XPATH, '//*[@id="main"]/div[3]/div/div[2]'
        )

        previous_height = 0
        previous_message_count = 0
        messages_elements = []

        got_the_oldest_messages = False
        sleep(random.randint(2, 5))
        while True:
            try:
                messages_elements = conversation_container.find_elements(
                    By.CSS_SELECTOR, ".message-in, .message-out"
                )

                if len(messages_elements) == 0:
                    break

                if len(messages_elements) == previous_message_count:
                    ws_msg = conversation_container.find_elements(
                        By.XPATH, "//div[contains(text(), 'Use WhatsApp on your phone to see older messages')]"
                    )
                    got_the_oldest_messages = len(ws_msg) == 0
                    contact.is_first_message = got_the_oldest_messages
                    break

                previous_message_count = len(messages_elements)
            except Exception as e:
                print(f"Error getting messages: {e}")
                break

            # get last message date
            try:
                last_message_date = None
                date_text = messages_elements[len(messages_elements) - 1].find_element(
                    By.CSS_SELECTOR, ".copyable-text").get_attribute(
                    "data-pre-plain-text")
                if date_text:
                    date_parts = date_text.split('] ')[
                        0].replace('[', '').split(', ')
                    time = date_parts[0]
                    date = date_parts[1]
                    last_message_date = convert_to_utc(date, time)

                # check if last message date is the same as the last message timestamp
                if last_message_date and contact.last_message_timestamp:
                    # Normalize both timestamps to ISO format for comparison
                    last_message_str = last_message_date.isoformat()
                    contact_message_str = contact.last_message_timestamp
                    if last_message_str == contact_message_str and not contact.try_to_get_messages_error:
                        print(
                            f"Last message date is the same as the last message timestamp, the messages are up to date...")
                        return contact.messages
            except Exception as e:
                print(f"Error getting last message date: {e}")

            try:
                print('Attempting to scroll')
                self.bot.driver.execute_script(
                    "arguments[0].scrollTop = 0;",
                    conversation_container
                )
                sleep(random.randint(1, 3))
            except Exception as e:
                print(f"Error scrolling: {e}")
                break

            try:
                older_messages_button = self.bot.driver.find_elements(
                    By.XPATH, "//button[.//div[contains(text(), 'Click here to get older messages')]]"
                )
                if older_messages_button:
                    try:
                        older_messages_button[0].click()
                        sleep(10)
                    except StaleElementReferenceException:
                        print(
                            "Stale element when clicking older messages button, continuing...")

            except Exception as e:
                print(f"Error getting older messages: {e}")

        # TODO: TRY GET ONLY THE MESSAGE WITH ERROR
        # TODO: GET ONLY NEW MESSAGES
        return self._get_all_message_info(messages_elements, contact)

    def check_media_unavailable_message(self):
        # Check for "Media message unavailable" dialog
        media_unavailable = self.bot.driver.find_elements(
            By.XPATH, "//h1[contains(text(), 'Media message unavailable')]"
        )
        if media_unavailable:
            # Click OK button
            ok_button = self.bot.driver.find_element(
                By.XPATH, "//button[.//div[contains(text(), 'OK')]]"
            )
            ok_button.click()
            sleep(1)

    def _get_all_message_info(self, messages_elements, contact: Contact):
        """Extract information from message elements"""
        messages = []
        if contact.db.delete_chat_history(contact.number):
            print(f"Chat history deleted for {contact.number}")
        else:
            print(f"Failed to delete chat history for {contact.number}")

        for index, message in enumerate(messages_elements):
            try:
                self.check_media_unavailable_message()

                time, date, sender, utc_dt, error = None, None, None, None, None

                # Check for quoted message
                quoted_message, error_quoted_message = self._get_quoted_message(
                    message)

                # Get message text and metadata
                text, time, date, sender, utc_dt, error_message = self._get_message_text_and_metadata(
                    message)

                error = error_message if error_message else error_quoted_message

                # Process attachments
                attachment_data, utc_dt_attach, time_attach, date_attach = self._process_attachments(
                    message)
                timestamp_utc = utc_dt.isoformat() if utc_dt else None
                timestamp_utc_attach = utc_dt_attach.isoformat() if utc_dt_attach else None
                message_data = json.dumps({
                    "text": text,
                    "time": time if not attachment_data else time_attach,
                    "date": date if not attachment_data else date_attach,
                    "sender": sender,
                    "quoted_message": quoted_message,
                    "attachment_data": attachment_data,
                    "timestamp_utc": timestamp_utc if not attachment_data else timestamp_utc_attach,
                    "error": error
                })
                print(
                    f"Processing message {index + 1}/{len(messages_elements)}")

                if error:
                    error_to_save = error
                elif attachment_data:
                    error_to_save = attachment_data.get("error")
                else:
                    error_to_save = None

                attach_type = attachment_data.get(
                    "type") if attachment_data else ""

                is_sent = contact.name == sender

                # Save each message immediately after processing
                saved = contact.db.save_chat_history(
                    contact.number, message_data, is_sent, attach_type, error_to_save)
                if not saved:
                    print(
                        f"Warning: Failed to save message {index + 1} to database")

                if index == 0:
                    contact.first_message_found = message_data
                    contact.first_message_found_timestamp = timestamp_utc
                    contact.db.save_contact(contact.number, contact.name, contact.created_at, contact.last_message, contact.last_message_timestamp, contact.first_message_found,
                                            contact.first_message_found_timestamp, contact.is_first_message, contact.received_receipt, contact.received_receipt_timestamp, contact.try_to_get_messages_error)

                elif index == len(messages_elements) - 1:
                    contact.last_message = message_data
                    contact.last_message_timestamp = timestamp_utc
                    contact.db.save_contact(contact.number, contact.name, contact.created_at, contact.last_message, contact.last_message_timestamp, contact.first_message_found,
                                            contact.first_message_found_timestamp, contact.is_first_message, contact.received_receipt, contact.received_receipt_timestamp, contact.try_to_get_messages_error)
                messages.append(message_data)

            except Exception as e:
                print(f"Error processing message {index + 1}: {e}")
                contact.try_to_get_messages_error = True
                # Continue processing remaining messages even if one fails
                continue

        return messages

    def _get_quoted_message(self, message):
        """Extract quoted message if present"""
        quoted_elements = message.find_elements(
            By.CSS_SELECTOR, "div[role='button'][aria-label='Quoted message']"
        )
        if quoted_elements:
            try:
                quoted_sender = quoted_elements[0].find_elements(
                    By.CSS_SELECTOR, "span[dir='auto']._ao3e"
                )
                quoted_text = quoted_elements[0].find_elements(
                    By.CSS_SELECTOR, "span.quoted-mention._ao3e"
                )
                if quoted_text:
                    return {
                        "sender": quoted_sender[0].text if quoted_sender else '',
                        "text": quoted_text[0].text
                    }, None
            except Exception as e:
                print(f"Error processing quoted message: {e}")
                return None, str(e)
        return None, None

    def _get_message_text_and_metadata(self, message):
        """Extract message text and metadata"""
        text = ''
        time = date = sender = utc_dt = error = None

        copyable_text = message.find_elements(
            By.CSS_SELECTOR, ".copyable-text"
        )
        if copyable_text:
            main_text_element = message.find_elements(
                By.CSS_SELECTOR, "span.selectable-text.copyable-text"
            )
            if main_text_element:
                try:
                    text = decode_latin(main_text_element[0].text.strip())
                except Exception as e:
                    print(f"Error processing main text: {e}")
                    error = str(e)

            try:
                date_text = copyable_text[0].get_attribute(
                    "data-pre-plain-text")
                if date_text:
                    date_parts = date_text.split('] ')[
                        0].replace('[', '').split(', ')
                    time = date_parts[0]
                    date = date_parts[1]
                    sender = date_text.split('] ')[1].replace(': ', '')
                    utc_dt = convert_to_utc(date, time)
            except Exception as e:
                print(f"Error processing date: {e}")
                error = str(e)

        return text, time, date, sender, utc_dt, error

    def _get_date_of_attach_msg(self, message):
        """Get date of attach message"""
        date_attach = None
        time_attach = None
        utc_dt_attach = None

        try:
            # Get message Y position
            message_location = message.location['y']

            # Find all date divs in parent container
            parent = message.find_element(By.XPATH, "./../../..")
            date_divs = parent.find_elements(
                By.CSS_SELECTOR, "div._amk4._amkb")

            # Find closest date div above message
            closest_date_div = None
            smallest_distance = float('inf')

            for date_div in date_divs:
                date_location = date_div.location['y']
                if date_location < message_location:
                    distance = message_location - date_location
                    if distance < smallest_distance:
                        smallest_distance = distance
                        closest_date_div = date_div

            if closest_date_div:
                date_text = closest_date_div.text

                if "Messages are end-to-end encrypted" in date_text:
                    return None, None, None

                # Convert text date to proper format
                today = datetime.now()

                # Handle different date formats
                if "TODAY" in date_text.upper():
                    date_attach = today.strftime("%d/%m/%Y")
                elif "YESTERDAY" in date_text.upper():
                    yesterday = today - timedelta(days=1)
                    date_attach = yesterday.strftime("%d/%m/%Y")
                elif any(day in date_text.upper() for day in ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]):
                    # Find the most recent occurrence of this weekday
                    weekday_names = ["MONDAY", "TUESDAY", "WEDNESDAY",
                                     "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
                    target_weekday = next(i for i, day in enumerate(
                        weekday_names) if day in date_text.upper())
                    current_weekday = today.weekday()
                    days_diff = (current_weekday - target_weekday) % 7
                    target_date = today - timedelta(days=days_diff)
                    date_attach = target_date.strftime("%d/%m/%Y")
                else:
                    # Assume it's already in correct format
                    date_attach = date_text

            # Look for time in attachment messages
            time_element = message.find_elements(
                By.CSS_SELECTOR, "span.x1rg5ohu.x16dsc37[dir='auto']")
            if time_element and time_element[0].text:
                time_attach = time_element[0].text

            # Convert to UTC if we have both date and time
            if date_attach and time_attach:
                local_tz = pytz.timezone('America/Sao_Paulo')
                datetime_str = f"{date_attach} {time_attach}"
                local_dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
                local_dt = local_tz.localize(local_dt)
                utc_dt_attach = local_dt.astimezone(pytz.UTC)

        except Exception as e:
            print(f"Error processing date/time: {e}")

        return utc_dt_attach, time_attach, date_attach

    def _process_attachments(self, message):
        """Process any attachments in the message"""
        from config import IMAGE_ANALYZE, PDF_ANALYZE, AUDIO_ANALYZE
        # Check for images
        image_elements = message.find_elements(
            By.CSS_SELECTOR, "img[data-testid='image-thumb'], img[class*='x15kfjtz']"
        )
        if image_elements and IMAGE_ANALYZE:
            utc_dt_attach, time_attach, date_attach = self._get_date_of_attach_msg(
                message)
            self.bot.driver.execute_script(
                "arguments[0].scrollIntoView(true);", image_elements[0])
            sleep(1)
            return self._process_image_attachment(image_elements[0]), utc_dt_attach, time_attach, date_attach
        elif image_elements and not IMAGE_ANALYZE:
            return {
                "type": "image",
                "size": None,
                "file_path": None,
                "content": None,
                "is_receipt": False,
                "error": "Image analysis disabled"
            }, None, None, None

        # Check for PDF
        pdf_elements = message.find_elements(
            By.CSS_SELECTOR, "div[role='button'][title^='Download']"
        )
        if pdf_elements and PDF_ANALYZE:
            utc_dt_attach, time_attach, date_attach = self._get_date_of_attach_msg(
                message)
            self.bot.driver.execute_script(
                "arguments[0].scrollIntoView(true);", pdf_elements[0])
            sleep(1)
            return self._process_pdf_attachment(pdf_elements[0]), utc_dt_attach, time_attach, date_attach
        elif pdf_elements and not PDF_ANALYZE:
            return {
                "type": "document",
                "name": None,
                "size": None,
                "file_type": "PDF",
                "content": None,
                "is_receipt": False,
                "error": "PDF analysis disabled"
            }, None, None, None

        # Check for audio
        download_audio_button = message.find_elements(
            By.CSS_SELECTOR, "button[aria-label='Download voice message']"
        )
        if download_audio_button and AUDIO_ANALYZE:
            self.bot.driver.execute_script(
                "arguments[0].scrollIntoView(true);", download_audio_button[0])
            sleep(1)
            download_audio_button[0].click()
            sleep(2)

        audio_play_button = message.find_elements(
            By.CSS_SELECTOR, 'button[aria-label="Play voice message"]'
        )
        duration_text = "0:00"
        if audio_play_button and AUDIO_ANALYZE:
            utc_dt_attach, time_attach, date_attach = self._get_date_of_attach_msg(
                message)
            self.bot.driver.execute_script(
                "arguments[0].scrollIntoView(true);", audio_play_button[0])
            sleep(1)
            duration_element = message.find_elements(
                By.CSS_SELECTOR, "div._ak8w"
            )
            if duration_element:
                duration_text = duration_element[0].text if duration_element else "0:00"

            return self._process_audio_attachment(audio_play_button, duration_text), utc_dt_attach, time_attach, date_attach
        elif audio_play_button and not AUDIO_ANALYZE:
            return {
                "type": "audio",
                "duration": duration_text,
                "transcription": None,
                "error": "Audio analysis disabled"
            }, None, None, None

        return None, None, None, None

    def _process_image_attachment(self, image_element):
        """Process image attachments"""
        try:
            # Scroll element into view first
            self.bot.driver.execute_script(
                "arguments[0].scrollIntoView(true);", image_element)
            sleep(1)  # Give time for scroll to complete

            media_download = self.bot.driver.find_elements(
                By.CSS_SELECTOR, '[data-icon="media-download"]'
            )
            if media_download:
                media_download[0].click()
                sleep(10)

            image_container = image_element.find_elements(
                By.XPATH, "./ancestor::div[@role='button']")

            if not image_container:
                return {
                    "type": "image",
                    "size": None,
                    "file_path": None,
                    "content": None,
                    "is_receipt": False,
                    "error": "No image container found"
                }

            try:
                size_button = image_container[0].find_elements(
                    By.CSS_SELECTOR, "button[class*='x6s0dn4'] span:last-child")
                file_size = size_button[0].text if size_button else None
            except Exception as e:
                print(f"Could not find image size: {e}")
                file_size = None

            def click_and_process_image():
                try:
                    img_elements = image_container[0].find_elements(
                        By.CSS_SELECTOR, "img[src^='blob:'], img[src^='http']")

                    if len(img_elements) < 1:
                        return {
                            "type": "image",
                            "size": None,
                            "file_path": None,
                            "content": None,
                            "is_receipt": False,
                            "error": "No image found"
                        }

                    # Scroll to ensure element is in view before clicking
                    self.bot.driver.execute_script(
                        "arguments[0].scrollIntoView(true);", img_elements[0])
                    sleep(1)

                    # Try clicking with JavaScript if regular click fails
                    try:
                        img_elements[0].click()
                    except:
                        self.bot.driver.execute_script(
                            "arguments[0].click();", img_elements[0])
                    sleep(2)

                    modal_img = self.bot.driver.find_elements(
                        By.CSS_SELECTOR,
                        "div.overlay img[src^='blob:']"
                    )
                    if not modal_img:
                        return {
                            "type": "image",
                            "size": None,
                            "file_path": None,
                            "content": None,
                            "is_receipt": False,
                            "error": "No image found"
                        }

                    location = modal_img[0].location
                    size = modal_img[0].size

                    screenshot = self.bot.driver.get_screenshot_as_png()
                    image = Image.open(io.BytesIO(screenshot))

                    dpr = self.bot.driver.execute_script(
                        'return window.devicePixelRatio')
                    left = location['x'] * dpr
                    top = location['y'] * dpr
                    right = (location['x'] + size['width']) * dpr
                    bottom = (location['y'] + size['height']) * dpr

                    image = image.crop((left, top, right, bottom))

                    text = pytesseract.image_to_string(image, lang='por')

                    from config import RECEIPT_KEYWORDS
                    is_receipt = is_receipt_by_keywords(text, RECEIPT_KEYWORDS)

                    file_path = os.path.join(
                        self.temp_dir,
                        f"image_{datetime.now().timestamp()}.png"
                    )
                    image.save(file_path)

                    ActionChains(self.bot.driver).send_keys(
                        Keys.ESCAPE).perform()
                    sleep(1)

                    return {
                        "type": "image",
                        "size": file_size,
                        "file_path": file_path,
                        "content": text,
                        "is_receipt": is_receipt
                    }
                except Exception as e:
                    print(f"Error processing image: {e}")
                    try:
                        ActionChains(self.bot.driver).send_keys(
                            Keys.ESCAPE).perform()
                    except:
                        pass
                    return None

            return click_and_process_image()

        except Exception as e:
            print(f"Error processing image attachment: {e}")
            try:
                # Always try to close modal if something goes wrong
                ActionChains(self.bot.driver).send_keys(Keys.ESCAPE).perform()
            except:
                pass
            return {
                "type": "image",
                "error": str(e),
                "is_receipt": False
            }

    def _save_messages_to_file(self, chat_name, messages):
        """Save messages to JSON file"""
        safe_filename = "".join(c if c.isalnum() or c in (
            '-', '_') else '_' for c in chat_name)
        output_file = os.path.join(
            self.output_dir, f"{safe_filename}.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    def _scroll_chats_list(self):
        """Scroll the chats list"""
        chat_list_element = self.bot.driver.find_element(By.ID, "pane-side")
        self.bot.driver.execute_script(
            "arguments[0].scrollTop = -arguments[0].scrollTop + 1000",
            chat_list_element
        )
        sleep(2)

    def _process_pdf_attachment(self, pdf_element):
        """Process PDF attachments"""
        try:
            # Click to start download
            pdf_element.click()
            sleep(2)

            # Get file name and size
            file_name = pdf_element.find_element(
                By.CSS_SELECTOR, "span.x13faqbe._ao3e").text
            file_size = pdf_element.find_element(
                By.CSS_SELECTOR, "span[title$='kB']").text

            # Wait for file to download
            max_wait = 30
            start_time = datetime.now()
            downloaded_file = None

            print(f"Waiting for PDF to download in {self.temp_dir}")
            while (datetime.now() - start_time).total_seconds() < max_wait:
                files = os.listdir(self.temp_dir)
                pdf_files = [f for f in files if f.endswith(
                    '.pdf') and not f.endswith('.crdownload')]
                if pdf_files:
                    downloaded_file = os.path.join(
                        self.temp_dir, pdf_files[0])
                    break
                sleep(1)

            if downloaded_file:
                from PyPDF2 import PdfReader
                reader = PdfReader(downloaded_file)
                pdf_content = ""

                for page in reader.pages:
                    pdf_content += page.extract_text()

                # Check if PDF content contains receipt keywords
                from config import RECEIPT_KEYWORDS
                is_receipt = is_receipt_by_keywords(
                    pdf_content, RECEIPT_KEYWORDS)

                if not is_receipt:
                    os.remove(downloaded_file)

                return {
                    "type": "document",
                    "name": file_name,
                    "size": file_size,
                    "file_type": "PDF",
                    "content": pdf_content,
                    "is_receipt": is_receipt
                }
            else:
                return {
                    "type": "document",
                    "name": file_name,
                    "size": file_size,
                    "file_type": "PDF",
                    "content": None,
                    "is_receipt": False,
                    "error": "Download failed"
                }

        except Exception as e:
            print(f"Error processing PDF: {e}")
            return {
                "type": "document",
                "error": str(e),
                "is_receipt": False
            }

    def _process_audio_attachment(self, play_button, duration_text):
        """Process audio attachments"""
        try:
            # Enable network interception
            self.bot.driver.execute_cdp_cmd('Performance.enable', {})
            self.bot.driver.execute_cdp_cmd('Network.enable', {})

            # Convert duration to seconds
            minutes, seconds = map(int, duration_text.split(':'))
            total_seconds = minutes * 60 + seconds
            wait_time = total_seconds + 2

            # Click play button
            play_button[0].click()
            sleep(wait_time)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Get performance logs
                    logs = self.bot.driver.get_log('performance')

                    # Find audio request
                    audio_request = None
                    for entry in logs:
                        try:
                            event = json.loads(entry['message'])['message']
                            if (event['method'] == 'Network.responseReceived' and
                                ('audio' in event['params']['response'].get('mimeType', '') or
                                    event['params']['type'] == 'Media')):
                                audio_request = event['params']
                                break
                        except Exception as e:
                            print(f"Error parsing log entry: {e}")
                            continue

                    if audio_request:
                        print(
                            f"Found audio request: {audio_request['requestId']}")
                        response = self.bot.driver.execute_cdp_cmd(
                            'Network.getResponseBody',
                            {'requestId': audio_request['requestId']}
                        )

                        if response and response.get('body'):
                            # Save raw audio data
                            audio_bytes = base64.b64decode(response['body'])
                            raw_path = os.path.join(
                                self.temp_dir,
                                f"audio_{datetime.now().timestamp()}.opus"
                            )

                            with open(raw_path, 'wb') as f:
                                f.write(audio_bytes)

                            # Convert to MP3
                            audio = AudioSegment.from_file(raw_path)
                            mp3_path = raw_path.replace('.opus', '.mp3')
                            audio.export(mp3_path, format="mp3")

                            # Clean up raw file
                            os.remove(raw_path)

                            # Transcribe audio
                            transcription = self._transcribe_audio(mp3_path)

                            # Clean up MP3 file
                            os.remove(mp3_path)

                            return {
                                "type": "audio",
                                "duration": duration_text,
                                "transcription": transcription
                            }

                except Exception as e:
                    print(
                        f"Error processing audio (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        print(f"Retrying... ({attempt + 1}/{max_retries})")
                    else:
                        print("Max retries reached")

            # Disable logging
            self.bot.driver.execute_cdp_cmd('Performance.disable', {})
            self.bot.driver.execute_cdp_cmd('Network.disable', {})

        except Exception as e:
            print(f"Error processing audio: {e}")
            try:
                self.bot.driver.execute_cdp_cmd('Performance.disable', {})
                self.bot.driver.execute_cdp_cmd('Network.disable', {})
            except:
                pass
            return {
                "type": "audio",
                "error": str(e)
            }

    def _transcribe_audio(self, audio_path):
        """Transcribe audio using Whisper"""
        try:
            # Try using MPS (Apple Silicon)
            model = WhisperModel("base", device="mps", compute_type="float16")
        except Exception as e:
            print(f"Error using MPS: {e}")
            print("Falling back to CPU...")
            # Fallback to CPU
            model = WhisperModel("base", device="cpu", compute_type="float32")

        segments, info = model.transcribe(audio_path, language="pt")
        return " ".join([segment.text for segment in segments])

    # def _restore_context(self):
    #     """Restore chat context after reconnection"""
    #     try:
    #         # Se estávamos em um chat específico, tentar voltar para ele
    #         if hasattr(self, '_current_chat_name'):
    #             # Procurar pela caixa de pesquisa
    #             search_box = self.bot.driver.find_element(
    #                 By.XPATH,
    #                 "//div[contains(@class, 'x1hx0egp')][@role='textbox']"
    #             )
    #             if search_box:
    #                 search_box.click()
    #                 search_box.send_keys(self._current_chat_name)
    #                 search_box.send_keys(Keys.ENTER)
    #                 sleep(2)
    #     except Exception as e:
    #         print(f"Error restoring context: {e}")

    # Adicionar aqui os outros métodos do notebook
    # get_all_messages(), process_image_attachment(), etc.
