import subprocess
import time
import os
import sys
import pyautogui
from PIL import ImageGrab

class DOSBoxController:
    def __init__(self, dosbox_path, dosbox_config, prn_files_dir, screenshot_dir,
                 mount_dir="C:/Temp", window_title="DOSBox"):
        self.dosbox_path = dosbox_path
        self.dosbox_config = dosbox_config
        self.prn_files_dir = prn_files_dir
        self.screenshot_dir = screenshot_dir
        self.mount_dir = mount_dir
        self.window_title = window_title
        self.resolution_prompted = False

        if not os.path.exists(self.dosbox_path):
            raise FileNotFoundError(f"DOSBox not found at: {self.dosbox_path}")
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def check_window(self):
        return bool(pyautogui.getWindowsWithTitle(self.window_title))

    def ensure_window(self):
        if not self.check_window():
            print("DOSBox window closed. Exiting script.")
            sys.exit()

    def launch(self):
        subprocess.Popen([self.dosbox_path, "-conf", self.dosbox_config])
        time.sleep(2)
        self.activate_window()

    def activate_window(self):
        self.ensure_window()
        window = pyautogui.getWindowsWithTitle(self.window_title)[0]
        window.activate()
        time.sleep(0.5)

    def send_keys(self, *keys, interval=0.1):
        for key in keys:
            pyautogui.press(key)
            time.sleep(interval)

    def type_command(self, command, interval=0.01, press_enter=True, extra_delay=0.5):
        pyautogui.write(command, interval=interval)
        time.sleep(extra_delay)
        if press_enter:
            pyautogui.press("enter")
        self.ensure_window()

    def take_screenshot(self, filename):
        try:
            window = pyautogui.getWindowsWithTitle(self.window_title)[0]
            left, top, width, height = window.left, window.top, window.width, window.height
            img = ImageGrab.grab(bbox=(left, top, left + width, top + height))
            filepath = os.path.join(self.screenshot_dir, filename)
            img.save(filepath)
            print(f"Screenshot saved: {filepath}")
        except Exception as e:
            print(f"Error capturing screenshot: {e}")

    def start_session(self):
        """Launch DOSBox, mount the directory, and start the CFA program."""
        self.launch()
        self.type_command(f"mount c {self.mount_dir}")
        self.type_command("c:")
        self.type_command("CFA", press_enter=False)
        self.send_keys("enter", "enter", "enter")

    def process_prn_file(self, prn_file):
        # From the main menu, select option 1 then 6 to start processing a file
        self.send_keys("1", "enter")
        time.sleep(0.5)
        self.send_keys("6", "enter")
        time.sleep(0.5)

        # Input the .prn file name and drive letter
        pyautogui.write(prn_file)
        self.send_keys("enter")
        pyautogui.write("C:")
        self.send_keys("enter")
        time.sleep(0.5)
        self.send_keys("enter")

        # Navigate the Frequency Analysis menus and take the first screenshot
        self.send_keys("7", "enter", "enter", "enter")
        self.send_keys("3", "enter", "enter", "enter", "enter")
        self.take_screenshot(f"01_{prn_file}_LP3.png")
        self.send_keys("enter", "enter")

        # Execute the screen resolution prompt only for the first file
        if not self.resolution_prompted:
            pyautogui.write("97,97")
            self.send_keys("enter", "enter", "enter")
            time.sleep(9.5)
            self.take_screenshot(f"02_{prn_file}_LP3_GRAPH.png")
            self.resolution_prompted = True
            self.send_keys("enter", interval=1)
            self.send_keys("enter", "enter")

        # Continue with the subsequent analysis steps and screenshots
        self.send_keys("4", "enter", "enter", "enter", "enter")
        self.take_screenshot(f"03_{prn_file}_WAKEBY.png")
        self.send_keys("enter", "enter", "enter", "enter")
        time.sleep(9.5)
        self.take_screenshot(f"04_{prn_file}_WAKEBY_GRAPH.png")
        self.send_keys("enter", interval=1)
        self.send_keys("enter", "enter")

        self.send_keys("1", "enter", "enter", "enter", "enter")
        self.take_screenshot(f"05_{prn_file}_GEV.png")
        self.send_keys("enter", "enter", "enter", "enter")
        time.sleep(9.5)
        self.take_screenshot(f"06_{prn_file}_GEV_GRAPH.png")
        self.send_keys("enter", interval=1)
        self.send_keys("enter", "enter")

        # Return to the main menu for the next file
        self.send_keys("1")

    def exit_session(self):
        """Close the DOSBox window after processing is complete."""
        pyautogui.hotkey("alt", "f4")

    def process_all_prn(self):
        prn_files = [f for f in os.listdir(self.prn_files_dir) if f.endswith(".prn")]
        if not prn_files:
            print("No .prn files found.")
            return

        # Start a single DOSBox session and initialize the CFA program
        self.start_session()

        # Process each .prn file from the main menu
        for prn in prn_files:
            print(f"Processing {prn}...")
            self.process_prn_file(prn)
            print(f"Finished processing {prn}.")

        # Exit the session after all files are processed
        self.exit_session()

if __name__ == "__main__":
    # Default paths (to be parameterized later via the GUI)
    dosbox_path = r"C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"
    dosbox_config = r"C:\Users\patel\AppData\Local\DOSBox\dosbox-0.74-3.conf"
    prn_files_dir = r"C:\Temp"
    screenshot_dir = r"C:\Temp"

    controller = DOSBoxController(dosbox_path, dosbox_config, prn_files_dir, screenshot_dir)
    controller.process_all_prn()
