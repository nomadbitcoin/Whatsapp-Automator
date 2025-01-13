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
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_messages (
            number TEXT PRIMARY KEY,
            name TEXT,
            message TEXT,
            timestamp DATETIME
        )
        ''')
        
        self.conn.commit()

    def save_message(self, number: str, name: str, message: str):
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
        """Retrieve all sent messages from the database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sent_messages')
        return cursor.fetchall()

    def close(self):
        """Close the database connection"""
        self.conn.close() 