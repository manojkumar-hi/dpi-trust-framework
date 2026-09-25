from playwright.sync_api import sync_playwright
import time
import os

ARTIFACTS_DIR = r"C:\Users\manoj\.gemini\antigravity-ide\brain\242ac533-ec6d-4190-bfbf-d6b7de54558e\scratch"

pages_to_capture = [
    {"name": "Dashboard", "url": "http://localhost:5173/"},
    {"name": "Agent_Registry", "url": "http://localhost:5173/agents"},
    {"name": "Credential_Registry", "url": "http://localhost:5173/credentials"},
    {"name": "Delegation_and_Authority", "url": "http://localhost:5173/delegations"},
    {"name": "Trust_Evaluation", "url": "http://localhost:5173/trust"},
    {"name": "Credential_Verification", "url": "http://localhost:5173/verification"},
    {"name": "Audit_and_Traceability", "url": "http://localhost:5173/audit"}
]

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for item in pages_to_capture:
            print(f"Capturing {item['name']} at {item['url']}...")
            try:
                page.goto(item['url'], wait_until='networkidle')
                time.sleep(2)  # Give React time to render
                screenshot_path = os.path.join(ARTIFACTS_DIR, f"{item['name']}.png")
                page.screenshot(path=screenshot_path)
                print(f"Saved {screenshot_path}")
            except Exception as e:
                print(f"Failed to capture {item['name']}: {e}")
        browser.close()

if __name__ == "__main__":
    capture()
