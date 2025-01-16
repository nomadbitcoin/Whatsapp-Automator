import sqlite3
from datetime import datetime
import os


class MessageDatabase:
    def __init__(self):
        # Ensure the data directory exists
        os.makedirs('data', exist_ok=True)

        # Connect to SQLite database (will create if not exists)
        self.db_path = 'data/messages.db'
        self.conn = sqlite3.connect(self.db_path)
        self.create_tables()

    def create_tables(self):
        """Create the necessary tables if they don't exist"""
        cursor = self.conn.cursor()

        # Create contacts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            number TEXT PRIMARY KEY,
            name TEXT,
            timestamp DATETIME,
            last_message TEXT,
            last_message_timestamp DATETIME,
            first_message_found TEXT,
            first_message_found_timestamp DATETIME,
            is_first_message BOOLEAN,
            received_receipt BOOLEAN,
            received_receipt_timestamp DATETIME,
            is_ws_business BOOLEAN
        )
        ''')

        # Create sent_messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            name TEXT,
            message TEXT,
            timestamp DATETIME
        )
        ''')

        # Create chat_history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            message JSON,
            timestamp DATETIME,
            is_sent BOOLEAN
        )
        ''')

        self.conn.commit()

    def save_sent_message(self, number: str, name: str, message: str):
        """
        Save a successfully sent message to the database

        Args:
            number (str): The recipient's phone number
            name (str): The recipient's name
            message (str): The message that was sent
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()

        try:
            cursor.execute('''
            INSERT OR REPLACE INTO sent_messages (number, name, message, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (number, name, message, timestamp))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving message to database: {e}")
            return False

    def get_all_sent_messages(self):
        """
        Retrieve all sent messages from the database

        Returns:
            list: A list of tuples containing all sent messages
                  Each tuple contains (id, number, name, message, timestamp)
            None: If there was an error retrieving the messages
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT * FROM sent_messages')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error retrieving sent messages: {e}")
            return None

    def get_all_chat_history_by_number(self, number: str):
        """
        Retrieve all chat history for a specific phone number

        Args:
            number (str): The phone number to retrieve chat history for

        Returns:
            list: A list of tuples containing all chat messages
                  Each tuple contains (id, number, message, timestamp, is_sent)
            None: If there was an error retrieving the chat history
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'SELECT * FROM chat_history WHERE number = ?', (number,))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error retrieving chat history: {e}")
            return None

    def save_chat_history(self, number: str, message: str, is_sent: bool):
        """
        Save a chat message to the history database

        Args:
            number (str): The phone number associated with the message
            message (str): The content of the message
            is_sent (bool): Whether the message was sent by the user (True) or received (False)

        Returns:
            bool: True if successful, False if there was an error
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        try:
            cursor.execute('INSERT INTO chat_history (number, message, timestamp, is_sent) VALUES (?, ?, ?, ?)',
                           (number, message, timestamp, is_sent))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving chat history: {e}")
            return False

    def save_contact(self, number: str, name: str, timestamp: str, last_message: str,
                     last_message_timestamp: str, first_message_found: str, first_message_found_timestamp: str,
                     is_first_message: bool, received_receipt: bool, received_receipt_timestamp: str):
        """
        Save or update a contact in the database

        Args:
            number (str): The contact's phone number
            name (str): The contact's name
            timestamp (str): The timestamp of when the contact was added/updated
            last_message (str): The most recent message
            last_message_timestamp (str): Timestamp of the last message
            first_message_found (str): The first message found
            first_message_found_timestamp (str): Timestamp of the first message
            is_first_message (bool): Whether we've found the first message
            received_receipt (bool): Whether we've received a receipt
            received_receipt_timestamp (str): Timestamp of the receipt

        Returns:
            bool: True if successful, False if there was an error
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO contacts 
                (number, name, timestamp, last_message, last_message_timestamp, 
                first_message_found, first_message_found_timestamp, is_first_message, 
                received_receipt, received_receipt_timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (number, name, timestamp, last_message, last_message_timestamp,
                  first_message_found, first_message_found_timestamp, is_first_message,
                  received_receipt, received_receipt_timestamp))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving contact: {e}")
            return False

    def get_all_contacts(self):
        """
        Retrieve all contacts from the database

        Returns:
            list: A list of tuples containing all contacts
                  Each tuple contains all contact fields from the database
            None: If there was an error retrieving the contacts
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT * FROM contacts ORDER BY timestamp DESC')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error retrieving contacts: {e}")
            return None

    def get_contact_by_number(self, number: str):
        """
        Retrieve a specific contact by their phone number

        Args:
            number (str): The phone number to search for

        Returns:
            tuple: A tuple containing all contact fields from the database
            None: If there was an error or the contact wasn't found
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'SELECT * FROM contacts WHERE number = ?', (number,))
            return cursor.fetchone()
        except Exception as e:
            print(f"Error retrieving contact: {e}")
            return None

    def close(self):
        """Close the database connection"""
        self.conn.close()
