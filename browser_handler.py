import functools
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException, TimeoutException, InvalidSessionIdException
from urllib3.exceptions import MaxRetryError, NewConnectionError
from requests.exceptions import ConnectionError
from time import sleep
import psutil
import os
import platform
import subprocess


def kill_chrome_processes():
    """Kill all Chrome processes across different operating systems"""
    system = platform.system().lower()

    if system == "windows":
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                           capture_output=True, check=False)
            subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'],
                           capture_output=True, check=False)
        except Exception as e:
            print(f"Error killing Chrome on Windows: {e}")

    elif system in ["linux", "darwin"]:  # Linux ou MacOS
        try:
            # Primeiro tenta usar pkill (mais seguro)
            try:
                subprocess.run(['pkill', '-f', 'chrome'],
                               capture_output=True, check=False)
                subprocess.run(['pkill', '-f', 'chromedriver'],
                               capture_output=True, check=False)
            except FileNotFoundError:
                # Se pkill não estiver disponível, usa killall
                subprocess.run(['killall', '-9', 'chrome'],
                               capture_output=True, check=False)
                subprocess.run(['killall', '-9', 'chromedriver'],
                               capture_output=True, check=False)

            # Processos específicos do Chrome no MacOS
            if system == "darwin":
                subprocess.run(['pkill', '-f', 'Google Chrome'],
                               capture_output=True, check=False)

        except Exception as e:
            print(f"Error killing Chrome on {system}: {e}")
            # Fallback para psutil se os comandos do sistema falharem
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if any(chrome_process in proc.info['name'].lower()
                           for chrome_process in ['chrome', 'chromedriver']):
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied,
                        psutil.ZombieProcess) as e:
                    print(f"Error with psutil: {e}")
    else:
        print(f"Unsupported operating system: {system}")


def retry_on_connection_error(max_retries=3, delay=2):
    """
    Decorator that handles browser connection errors by:
    1. Retrying the operation
    2. Reconnecting if needed
    3. Killing zombie processes if needed
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except (WebDriverException, StaleElementReferenceException) as e:
                    print(f"Browser error on attempt {attempt + 1}: {str(e)}")

                    if attempt < max_retries - 1:
                        print("Attempting to reconnect...")
                        try:
                            # Tenta fechar o driver atual
                            self.bot.quit_driver()
                        except:
                            pass

                        # Mata processos Chrome zumbis
                        # kill_chrome_processes()

                        sleep(delay)

                        # Reinicializa o driver
                        self.bot.login()

                        # Navega de volta para o estado anterior
                        # Isso dependerá do contexto - você pode precisar adicionar lógica específica aqui
                        print("Reconnected. Retrying operation...")
                    else:
                        print("Max retries reached. Operation failed.")
                        raise
            return None
        return wrapper
    return decorator
