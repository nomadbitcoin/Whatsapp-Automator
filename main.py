from driver import Bot, Fore, Style
import sys
import os

PREFIX = "55"  # The national prefix without the +

def list_chrome_sessions():
    """Lists all available Chrome sessions and allows creating a new one"""
    chrome_data_dir = os.path.join(os.getcwd(), 'chrome-data')
    
    # Debug prints
    print(f"\nLooking for sessions in: {chrome_data_dir}")
    
    # Create chrome-data directory if it doesn't exist
    if not os.path.exists(chrome_data_dir):
        print("Creating chrome-data directory as it doesn't exist")
        os.makedirs(chrome_data_dir)
    
    # Get list of existing sessions
    sessions = []
    try:
        sessions = [d for d in os.listdir(chrome_data_dir) 
                   if os.path.isdir(os.path.join(chrome_data_dir, d))]
        print(f"Found {len(sessions)} existing sessions: {sessions}")
    except Exception as e:
        print(f"Error listing sessions: {e}")
    
    print("\nAvailable sessions:")
    print("0) Create new session")
    for idx, session in enumerate(sessions, 1):
        print(f"{idx}) {session}")
    
    while True:
        try:
            choice = int(input("\nSelect a session (0-{}): ".format(len(sessions))))
            if choice == 0:
                # Create new session
                while True:
                    new_session = input("Enter name for new session: ").strip()
                    new_session_path = os.path.join(chrome_data_dir, new_session)
                    if os.path.exists(new_session_path):
                        print(Fore.RED + "Session already exists. Choose another name." + Style.RESET_ALL)
                    elif new_session and all(c.isalnum() or c in '_-' for c in new_session):
                        os.makedirs(new_session_path)
                        print(f"Created new session directory: {new_session_path}")
                        return new_session
                    else:
                        print(Fore.RED + "Invalid session name. Use only letters, numbers, underscore and hyphen." + Style.RESET_ALL)
            elif 1 <= choice <= len(sessions):
                return sessions[choice-1]
            else:
                print(Fore.RED + "Invalid choice. Please try again." + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "Please enter a number." + Style.RESET_ALL)


class Menu:
    def __init__(self):
        self.session_name = list_chrome_sessions()
        self.bot = None
        self.choices = {
            "1": self.send_message,
            "2": self.send_with_media,
            "3": self.quit,
            "4": self.count_whatsapp_chats,
            "5": self.generate_csv_from_chat,
            "6": self.generate_chat_history,
        }

    def create_bot(self):
        """Creates a new bot instance with the selected session"""
        return Bot(session_name=self.session_name)

    def display(self):
        try:
            assert PREFIX != "" and "+" not in PREFIX
            print("\nWHATSAPP AUTOMATOR")
            print(Fore.YELLOW + f"Current session: {self.session_name}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"You have chosen this number prefix: {PREFIX}" + Style.RESET_ALL)
            print("""
                1. Send messages
                2. Send messages with media attached
                3. Quit
                4. Count WhatsApp chats
                5. Generate CSV from chat history
                6. Extract chat history
            """)
        except AssertionError:
            print(Fore.RED + "Please fill the PREFIX variable in main.py OR remove the + in the PREFIX." + Style.RESET_ALL)
            sys.exit(1)

    def settings(self):
        print("- Select the file to use for the message:")
        txt = self.load_file("txt")

        print("- Select the file to use for the numbers:")
        csv = self.load_file("csv")

        include_names = None
        while include_names not in ["y", "n"]:
            include_names = input(
                "- Include names in the messages? Y/N\n> ").lower()

        include_names = True if include_names == "y" else False

        return csv, txt, include_names

    def send_message(self):
        print(Fore.GREEN + "SEND MESSAGES" + Style.RESET_ALL)
        csv, txt, include_names = self.settings()
        print("Ready to start sending messages.")
        self.bot = self.create_bot()
        self.bot.csv_numbers = os.path.join("data", csv)
        self.bot.message = os.path.join("data", txt)
        self.bot.options = [include_names, False]
        print("PREFIX", PREFIX)
        self.bot.login(PREFIX)

    def send_with_media(self):
        print(Fore.GREEN + "SEND MESSAGES WITH MEDIA" + Style.RESET_ALL)
        input(Fore.YELLOW + "Please COPY the media you want to send with CTRL+C, then press ENTER." + Style.RESET_ALL)
        csv, txt, include_names = self.settings()
        print("Ready to start sending messages with media.")
        self.bot = self.create_bot()
        self.bot.csv_numbers = os.path.join("data", csv)
        self.bot.message = os.path.join("data", txt)
        self.bot.options = [include_names, True]
        self.bot.login(PREFIX)

    def load_file(self, filetype):
        selection = 0
        idx = 1
        files = {}

        for file in os.listdir("data"):
            if file.endswith("." + filetype):
                files[idx] = file
                print(idx, ") ", file)
                idx += 1

        if len(files) == 0:
            raise FileNotFoundError

        while selection not in files.keys():
            selection = int(input("> "))

        return str(files[selection])

    def quit(self):
        print("If you like this script, please donate.")
        print("Send MATIC, BEP20, ERC20, BTC, BCH, CRO, LTC, DASH, CELO, ZEC, XRP to:")
        print(Fore.GREEN, "landifrancesco.wallet", Style.RESET_ALL)
        sys.exit(0)

    def count_whatsapp_chats(self):
        """
        Initialize bot and count WhatsApp chats without sending messages
        """
        print(Fore.GREEN + "COUNTING WHATSAPP CHATS" + Style.RESET_ALL)
        self.bot = self.create_bot()
        self.bot.login_and_count_chats()
        input("\nPress Enter to return to menu...")
        self.bot.quit_driver()

    def click_first_chat_and_scroll(self):
        """
        Initialize bot and click first chat then scroll up
        """
        print(Fore.GREEN + "CLICKING FIRST CHAT AND SCROLLING" + Style.RESET_ALL)
        self.bot = Bot()
        self.bot.click_first_chat_and_scroll()
        input("\nPress Enter to return to menu...")
        self.bot.quit_driver()

    def generate_csv_from_chat(self):
        """
        Initialize bot and generate CSV from chat history
        """
        print(Fore.GREEN + "GENERATING CSV FROM CHAT HISTORY" + Style.RESET_ALL)
        self.bot = self.create_bot()
        self.bot.generate_chat_history_csv()
        input("\nPress Enter to return to menu...")
        self.bot.quit_driver()

    def generate_chat_history(self):
        """Extract and save chat history"""
        print(Fore.GREEN + "EXTRACTING CHAT HISTORY" + Style.RESET_ALL)
        self.bot = Bot()
        self.bot.login()

        from chat_extractor import ChatExtractor
        extractor = ChatExtractor(self.bot)
        chats = extractor.extract_all_chats()

        print(f"\nExtracted {len(chats)} chats")
        print("Chat histories saved to individual JSON files")

        input("\nPress Enter to return to menu...")
        self.bot.quit_driver()

    def run(self):
        while True:
            self.display()
            choice = input("Enter an option: ")
            action = self.choices[choice]
            if action:
                action()
                self.quit()
            else:
                print(Fore.RED, choice, " is not a valide choice")
                print(Style.RESET_ALL)


m = Menu()
m.run()
