import json
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
            created_at DATETIME,
            updated_at DATETIME,
            last_message JSON,
            last_message_timestamp DATETIME,
            first_message_found JSON,
            first_message_found_timestamp DATETIME,
            is_first_message BOOLEAN,
            received_receipt BOOLEAN,
            received_receipt_timestamp DATETIME,
            is_ws_business BOOLEAN,
            try_to_get_messages_error BOOLEAN
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
            is_sent BOOLEAN,
            attach_type TEXT,
            error TEXT
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

    def csv_from_chat_history(self):
        """
        Generates CSV file from chat_history table

        Returns:
            str: Path to the generated CSV file
            None: If there was an error generating the CSV
        """
        cursor = self.conn.cursor()
        try:
            # Ensure the data directory exists
            os.makedirs('data/exports', exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_path = f'data/exports/chat_history_{timestamp}.csv'

            # Get all data from chat_history
            cursor.execute('''
                SELECT number, message, timestamp, is_sent, error 
                FROM chat_history 
                ORDER BY timestamp
            ''')

            # Write to CSV file
            with open(csv_path, 'w', encoding='utf-8') as f:
                # Write header
                f.write('number,message,timestamp,is_sent,error\n')

                # Write data rows
                for row in cursor.fetchall():
                    # Replace any commas in the message with spaces to avoid CSV issues
                    message = str(row[1]).replace(',', ' ')
                    error = str(row[4]).replace(',', ' ') if row[4] else ''

                    f.write(f'{row[0]},{message},{row[2]},{row[3]},{error}\n')

            return csv_path

        except Exception as e:
            print(f"Error generating CSV file: {e}")
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

    def save_chat_history(self, number: str, message: json, is_sent: bool, attach_type: str, error: str):
        """
        Save a chat message to the history database

        Args:
            number (str): The phone number associated with the message
            message (str): The content of the message
            is_sent (bool): Whether the message was sent by the user (True) or received (False)
            attach_type (str): The type of attachment
            error (str): The error message if there was an error
        Returns:
            bool: True if successful, False if there was an error
        """
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        try:
            cursor.execute('INSERT INTO chat_history (number, message, timestamp, is_sent, attach_type, error) VALUES (?, ?, ?, ?, ?, ?)',
                           (number, message, timestamp, is_sent, attach_type, error))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving chat history: {e}")
            return False

    def delete_chat_history(self, number: str):
        """
        Delete all chat history for a specific phone number

        Args:
            number (str): The phone number to delete chat history for

        Returns:
            bool: True if successful, False if there was an error
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'DELETE FROM chat_history WHERE number = ?', (number,))
            cursor.execute(
                'UPDATE contacts SET last_message = NULL, last_message_timestamp = NULL, first_message_found = NULL, first_message_found_timestamp = NULL, is_first_message = FALSE, received_receipt = FALSE, received_receipt_timestamp = NULL, try_to_get_messages_error = FALSE WHERE number = ?', (number,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting chat history: {e}")
            return False

    def save_contact(self, number: str, name: str, timestamp: str, last_message: str,
                     last_message_timestamp: str, first_message_found: str, first_message_found_timestamp: str,
                     is_first_message: bool, received_receipt: bool, received_receipt_timestamp: str,
                     try_to_get_messages_error: bool):
        """
        Save or update a contact in the database        
        Args:
            number (str): The contact's phone number
            name (str): The contact's name
            created_at (str): The timestamp of when the contact was added
            updated_at (str): The timestamp of when the contact was updated
            last_message (str): The most recent message
            last_message_timestamp (str): Timestamp of the last message
            first_message_found (str): The first message found
            first_message_found_timestamp (str): Timestamp of the first message
            is_first_message (bool): Whether we've found the first message
            received_receipt (bool): Whether we've received a receipt
            received_receipt_timestamp (str): Timestamp of the receipt
            try_to_get_messages_error (bool): Whether there was an error trying to get messages
        Returns:
            bool: True if successful, False if there was an error
        """
        cursor = self.conn.cursor()
        try:
            current_time = datetime.now().isoformat()
            cursor.execute('''
                INSERT OR REPLACE INTO contacts 
                (number, name, created_at, updated_at, last_message, last_message_timestamp, 
                first_message_found, first_message_found_timestamp, is_first_message, 
                received_receipt, received_receipt_timestamp, is_ws_business, try_to_get_messages_error) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (number, name, current_time, current_time, last_message, last_message_timestamp,
                  first_message_found, first_message_found_timestamp, is_first_message,
                  received_receipt, received_receipt_timestamp, False, try_to_get_messages_error))
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
