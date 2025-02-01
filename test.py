import subprocess
import time
import pyautogui
import os
from PIL import ImageGrab, ImageChops
import sys

# Paths (using raw strings to avoid escape sequence issues)
dosbox_path = r"C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"  # Update this path
cfa_path = r"C:\Temp"  # Path to CFA program and .prn files
prn_files_dir = r"C:\Temp"  # Directory containing .prn files
dosbox_config = r"C:\Users\patel\AppData\Local\DOSBox\dosbox-0.74-3.conf"  # Path to DOSBox configuration file
screenshot_dir = r"C:\Temp"  # Directory to save screenshots

# Verify that DOSBox exists at the specified path
if not os.path.exists(dosbox_path):
    raise FileNotFoundError(f"DOSBox not found at: {dosbox_path}")

# Create screenshot directory if it doesn't exist7
if not os.path.exists(screenshot_dir):
    os.makedirs(screenshot_dir)


def check_dosbox_window(window_title="DOSBox"):
    """
    Checks if the DOSBox window is still open.

    Args:
        window_title (str): The title of the DOSBox window (default is "DOSBox").

    Returns:
        bool: True if the window is open, False otherwise.
    """
    try:
        # Find the DOSBox window by its title
        pyautogui.getWindowsWithTitle(window_title)[0]
        return True
    except IndexError:
        # Window not found
        return False

# Function to simulate keystrokes with delays
def send_keys(*keys, interval=0.1):
    """
    Simulates pressing multiple keys with a delay between each key press.

    Args:
        *keys: Variable number of keys to press (e.g., "enter", "1", "a").
        interval (float): Delay between key presses in seconds (default is 0.1).
    """
    for key in keys:
        pyautogui.press(key)
        time.sleep(interval)

    # Function to take a screenshot and save it


def take_screenshot(filename, window_title="DOSBox", timeout=30):
    """
    Captures a screenshot of the specified window once the graph is fully prepared.

    Args:
        filename (str): The name of the file to save the screenshot.
        window_title (str): The title of the window to capture (default is "DOSBox").
        timeout (int): Maximum time to wait for the graph to be prepared (default is 30 seconds).
    """
    try:
        # Find the CFA (DOSBox) window by its title
        cfa_window = pyautogui.getWindowsWithTitle(window_title)[0]

        # Get the window's position and size
        left, top, width, height = cfa_window.left, cfa_window.top, cfa_window.width, cfa_window.height

        # Capture the initial screenshot
        previous_screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))

        start_time = time.time()
        while time.time() - start_time < timeout:
            # Wait for a short interval
            time.sleep(1)

            # Capture the current screenshot
            current_screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))

            # Compare the current screenshot with the previous one
            difference = ImageChops.difference(previous_screenshot, current_screenshot)
            if not difference.getbbox():  # No difference between screenshots
                # Graph is fully prepared, save the final screenshot
                current_screenshot.save(filename)
                print(f"Screenshot saved: {filename}")
                return

            # Update the previous screenshot
            previous_screenshot = current_screenshot

        # If the loop ends due to timeout, save the last screenshot
        current_screenshot.save(filename)
        print(f"Screenshot saved (timeout reached): {filename}")
    except IndexError:
        print(f"Window with title '{window_title}' not found. Ensure the CFA window is open.")
    except Exception as e:
        print(f"Error capturing screenshot: {e}")

# Function to process a single .prn file
def process_prn_file(prn_file, resolution_prompted=False):
    # Launch CFA in DOSBox
    subprocess.Popen([dosbox_path, "-conf", dosbox_config])
    time.sleep(2)  # Wait for DOSBox to launch (increase delay if needed)

    # Bring DOSBox window into focus
    try:
        dosbox_window = pyautogui.getWindowsWithTitle("DOSBox")[0]
        dosbox_window.activate()
    except IndexError:
        raise Exception("DOSBox window not found. Ensure DOSBox is running and the window title is correct.")
    time.sleep(0.5)  # Wait for the window to come into focus

    # Mount C:\Temp to C: in DOSBox (using forward slashes)
    if not check_dosbox_window():
    # Mount C:\Temp to C: in DOSBox (using forward slashes)
        print("DOSBox window closed. Exiting script.")
        sys.exit()

    pyautogui.write("mount c C:/Temp", interval=0.01)  # Type the mount command with a delay between keystrokes
    time.sleep(0.5)  # Small delay to ensure the command is fully typed
    pyautogui.press("enter")  # Press Enter to execute the command

    if not check_dosbox_window():
        print("DOSBox window closed. Exiting script.")
        sys.exit()

    # Switch to C: drive
    pyautogui.write("c:", interval=0.01)  # Type c: with a delay between keystrokes
    time.sleep(0.5)  # Small delay to ensure the command is fully typed
    pyautogui.press("enter")  # Press Enter to switch to C:
    pyautogui.write("CFA", interval=0.01)

    # Press Enter twice
    send_keys("enter", "enter", "enter", interval = 0.1)

    # Main Menu: Press 1, then 6
    pyautogui.press("1")
    pyautogui.press("enter")
    time.sleep(0.5)
    pyautogui.press("6")
    pyautogui.press("enter")
    time.sleep(0.5)

    # Enter .prn file name and drive
    pyautogui.write(prn_file)  # Enter .prn file name
    send_keys("enter")
    pyautogui.write("C:")  # Enter drive letter
    send_keys("enter")

    # Wait for processing
    time.sleep(0.5)

    # Press Enter again to return to main menu
    send_keys("enter")

    # Go to Frequency Analysis Main Menu: Press 7, then Enter three times
    send_keys("7", "enter", "enter", "enter", interval = 0.1)

    # Frequency Analysis Main Screen: Press 3, then Enter four times
    send_keys("3", "enter", "enter", "enter", "enter", interval = 0.1)
    take_screenshot(f"01_{prn_file}_LP3.png")  # Take screenshot
    send_keys("enter", "enter")  # Press Enter twice

    # Graph Resolution Prompt (Only Once per Session)
    if not resolution_prompted:
        pyautogui.write("97,97")  # Enter resolution
        send_keys("enter", "enter", "enter", interval = 0.1)
        # Wait for processing
        take_screenshot(f"02_{prn_file}_LP3_GRAPH.png")  # Take screenshot
        resolution_prompted = True
        send_keys("enter", interval = 1)
        send_keys( "enter", "enter", interval = 0.1)

    # Continue Frequency Analysis: Press 4, then Enter four times
    send_keys("4", "enter", "enter", "enter", "enter", interval = 0.1)
    take_screenshot(f"03_{prn_file}_WAKEBY.png")  # Take screenshot
    send_keys("enter", "enter", "enter", "enter", interval = 0.1)  # Press Enter four times
    # Wait for processing
    take_screenshot(f"04_{prn_file}_WAKEBY_GRAPH.png")  # Take screenshot
    send_keys("enter", interval=1)
    send_keys("enter", "enter", interval=0.1)

    # Return to Frequency Analysis Main Screen: Press 1, then Enter four times
    send_keys("1", "enter", "enter", "enter", "enter", interval = 0.1)
    take_screenshot(f"05_{prn_file}_GEV.png")  # Take screenshot
    send_keys("enter", "enter", "enter", "enter", interval = 0.1)  # Press Enter four times
    # Wait for processing
    take_screenshot(f"06_{prn_file}_GEV_GRAPH.png")  # Take screenshot
    send_keys("enter", interval=1)
    send_keys("enter", "enter", interval=0.1)

    # Return to Main Window Screen: Press 1
    send_keys("1")

    # Close DOSBox
    pyautogui.hotkey("alt", "f4")

    return resolution_prompted

# Main function
def main():
    # Get list of .prn files
    prn_files = [f for f in os.listdir(prn_files_dir) if f.endswith(".prn")]
    resolution_prompted = False

    # Process each .prn file
    for prn_file in prn_files:
        print(f"Processing {prn_file}...")
        resolution_prompted = process_prn_file(prn_file, resolution_prompted)
        print(f"Finished processing {prn_file}.")

if __name__ == "__main__":
    main()