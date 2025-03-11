"""
This module continuously checks a Rezervanto appointment link for new timeslots, and sends an email to the user if new timeslots are available.
"""

import json
import os

from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import time

WEEKS_TO_CHECK: int = 5 # Number of weeks to check
WAIT_TIME: int = 15 # Time to wait between each check in minutes
GECKODRIVER_PATH: str = r'./bin/geckodriver.exe' # Path to the geckodriver executable
STATE_FILE: str = "state.json" # File to store the previous state of the timeslots

GO_TO_CALENDAR_MAIN = [ # Steps to take to navigate to the main calendar page
    {"by": By.ID, "value": "service-52025-", "description": "Následná kontrola"},
    {"by": By.ID, "value": "nextPage", "description": "Další krok"}
]

GO_TO_CALENDAR_TEST = [ # Steps to take to navigate to the test calendar page
    {"by": By.CSS_SELECTOR, "value": 'li.resource.tooltipstered[onclick*="16376"]', "description": "Test resource button for 16376"},
    {"by": By.CSS_SELECTOR, "value": "div#service-49398-", "description": "Terapie service button"},
    {"by": By.ID, "value": "nextPage", "description": "Další krok"}
]

GO_NEXT_WEEK = [ # Steps to take to navigate to the next week
    {"by": By.CSS_SELECTOR, "value": "#calendar-right .load", "description": "Next week arrow"}
]

def load_state():
    """Load the persistent state from the JSON file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    else:
        # Return a default state if the file doesn't exist
        return {"last_known_timeslot_count": 0}

def save_state(state):
    """Save the current state to the JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def execute_clicks(driver, steps):
    '''Executes a series of clicks on the webpage.'''

    for step in steps:
        try:
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((step["by"], step["value"]))
            )
            element.click()
            print(f"Clicked on {step['description']}")
            time.sleep(1)

        except Exception as e:
            print(f"Error clicking on {step['description']}: {e}")
            break

def get_timeslot_count(driver):
    '''Returns the number of available timeslots in the current week shown.'''

    clickable_elements = driver.find_elements(By.CSS_SELECTOR, "td.clickable")
    print(f"Found {len(clickable_elements)} available timeslots.")
    return len(clickable_elements)

def send_email(subject, body):
    """Sends an email using SendGrid."""
    
    # Retrieve credentials and email addresses from environment variables.
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    to_email = os.environ.get("SENDGRID_TO_EMAIL")
    
    if not api_key or not from_email or not to_email:
        raise ValueError("SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, and SENDGRID_TO_EMAIL must be set in your environment.")

    message = Mail(
        from_email = from_email,
        to_emails = to_email,
        subject = subject,
        plain_text_content = body
    )
    
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Email sent. Status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():

    # Load the environment variables
    load_dotenv()
    LINK = os.environ.get("TEST_LINK")

    # Load persistent state
    state = load_state()
    current_timeslot_count = 0

    # Create a Service object for geckodriver.
    service = Service(GECKODRIVER_PATH)

    # Initialize the webdriver
    driver = webdriver.Firefox(service=service)
    driver.get(LINK)

    # Navigate to the correct subpage
    execute_clicks(driver, GO_TO_CALENDAR_TEST)

    # For each week in WEEKS_TO_CHECK:

    for week in range(WEEKS_TO_CHECK):
        count = get_timeslot_count(driver)
        current_timeslot_count += count

        if week < WEEKS_TO_CHECK - 1:
            execute_clicks(driver, GO_NEXT_WEEK)
            time.sleep(2)

    print (f"Found {current_timeslot_count} timeslots in the next {WEEKS_TO_CHECK} weeks.")

    # If the number of timeslots has increased, send an email to the user
    previous_timeslot_count = state.get("last_known_timeslot_count", 0)

    if current_timeslot_count > previous_timeslot_count:
        print("Detected new timeslots. Sending email to user.")
        subject = "New Timeslots Available!"
        body = (f"The number of available timeslots increased from {previous_timeslot_count} "
                f"to {current_timeslot_count}.\nCheck the Rezervanto page for details.")
        send_email(subject, body)

    state["last_known_timeslot_count"] = current_timeslot_count
    save_state(state)

    driver.quit()

if __name__ == "__main__":
    main()

