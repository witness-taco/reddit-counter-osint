import asyncio
import json
import logging
import os
import random
import time
import nodriver as uc
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("nodriver.core.connection").setLevel(logging.CRITICAL)

PROFILE_DIR = os.path.expanduser('~/.config/nodriver_reddit_profile')
TARGET_URL = "https://www.reddit.com/"
LOG_FILE = "agent_training_metrics.json"

def log_training_result(phase, success, details=""):
    """Logs the success/failure rates of the HITL training phases."""
    log_entry = {"timestamp": time.time(), "phase": phase, "success": success, "details": details}
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f: logs = json.load(f)
        except: pass
    logs.append(log_entry)
    with open(LOG_FILE, 'w') as f: json.dump(logs, f, indent=4)

async def inject_observers(page):
    """Injects JS observers capturing viewport-relative coordinates and advanced signatures."""
    await page.evaluate("""
        window.clickSignatures = [];
        window.lastClickRelCoords = {relX: 0, relY: 0};
        
        document.addEventListener('click', function(e) {
            if (e.clientX === 0 && e.clientY === 0) return;
            
            window.lastClickRelCoords = {
                relX: e.clientX / window.innerWidth, 
                relY: e.clientY / window.innerHeight
            };
            
            const path = e.composedPath();
            for (let node of path) {
                if (node && node.nodeType === Node.ELEMENT_NODE) {
                    let tag = node.tagName.toLowerCase();
                    let role = node.getAttribute('role');
                    
                    if (tag === 'button' || role === 'button' || role === 'menuitem') {
                        // Capture aria-label first, fallback to innerText for dropdowns
                        let sig = node.getAttribute('aria-label') || node.innerText;
                        if (sig && sig.trim() !== "") { 
                            // Clean up newlines if innerText grabbed child spans
                            window.clickSignatures.push(sig.split('\\n')[0].trim()); 
                            return; 
                        }
                    }
                }
            }
        }, {capture: true});
    """)

async def fetch_js_data(page, variable_name):
    raw_data = await page.evaluate(f"JSON.stringify({variable_name})")
    if isinstance(raw_data, dict) and 'value' in raw_data:
        raw_data = raw_data['value']
    try: return json.loads(raw_data) if raw_data else None
    except: return None

async def synthetic_mouse_move(page, rel_x, rel_y):
    """Moves the hardware-level ghost mouse without clicking."""
    viewport = await fetch_js_data(page, "{w: window.innerWidth, h: window.innerHeight}")
    x, y = int(rel_x * viewport['w']), int(rel_y * viewport['h'])
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseMoved", x=x, y=y))
    await asyncio.sleep(0.2)

async def synthetic_mouse_click(page, rel_x, rel_y):
    """Executes relative coordinate click with visual debugger."""
    viewport = await fetch_js_data(page, "{w: window.innerWidth, h: window.innerHeight}")
    x, y = int(rel_x * viewport['w']), int(rel_y * viewport['h'])
    
    logger.info("Agent: Mapped ghost mouse to X:%s, Y:%s...", x, y)
    
    await page.evaluate(f"""
        let dot = document.createElement('div');
        dot.style.position = 'fixed'; dot.style.left = '{x}px'; dot.style.top = '{y}px';
        dot.style.width = '14px'; dot.style.height = '14px'; dot.style.backgroundColor = '#00ff00';
        dot.style.border = '2px solid black'; dot.style.borderRadius = '50%';
        dot.style.zIndex = '999999'; dot.style.pointerEvents = 'none';
        dot.style.transform = 'translate(-50%, -50%)'; document.body.appendChild(dot);
        setTimeout(() => dot.remove(), 3000);
    """)
    
    left_btn = uc.cdp.input_.MouseButton.LEFT
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseMoved", x=x, y=y))
    await asyncio.sleep(random.uniform(0.3, 0.6))
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mousePressed", x=x, y=y, button=left_btn, click_count=1))
    await asyncio.sleep(random.uniform(0.08, 0.15))
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseReleased", x=x, y=y, button=left_btn, click_count=1))

async def execute_dom_click(page, signature, step_name):
    """Helper to click DOM nodes and handle failures gracefully."""
    logger.info("Agent: Searching for %s ('%s')...", step_name, signature)
    target = await page.find(signature, timeout=4)
    if target:
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await target.click()
        return True
    logger.error("Agent: Failed to locate %s.", step_name)
    return False

async def main():
    os.makedirs(PROFILE_DIR, exist_ok=True)
    browser = await uc.start(headless=False, browser_executable_path='/usr/bin/google-chrome', user_data_dir=PROFILE_DIR)
    page = await browser.get(TARGET_URL)
    
    print("\n" + "="*60 + "\nPHASE 1: SETUP\n" + "="*60)
    await asyncio.to_thread(input, "Navigate to Comments. Press ENTER when ready.")
    await inject_observers(page)

    # --- STEP A: MENU TRAINING ---
    menu_sig = None
    while not menu_sig:
        print("\n--- STEP A: THE 3-DOT MENU ---")
        await asyncio.to_thread(input, "Click the 3-dot menu. Press ENTER.")
        
        sigs = await fetch_js_data(page, "window.clickSignatures")
        if sigs:
            menu_sig = Counter([s for s in sigs if "delete" not in s.lower()]).most_common(1)[0][0] if any("delete" not in s.lower() for s in sigs) else Counter(sigs).most_common(1)[0][0]
            
            # Dismiss menu and test
            body = await page.select('body')
            if body: await body.click()
            await asyncio.sleep(1)
            
            if await execute_dom_click(page, menu_sig, "Menu"):
                ans = await asyncio.to_thread(input, "Did the menu open? (Y/N): ")
                if ans.strip().upper() == 'Y': log_training_result("Step_A", True, menu_sig)
                else: 
                    menu_sig = None
                    log_training_result("Step_A", False, "User rejected")
                    await page.reload()
                    await asyncio.sleep(3)
                    await inject_observers(page)

    # --- STEP B: DROPDOWN TRAINING ---
    dropdown_sig = None
    while not dropdown_sig:
        print("\n--- STEP B: THE DROPDOWN ---")
        await asyncio.to_thread(input, "Menu is open. Click 'Delete' in the dropdown. Press ENTER.")
        
        sigs = await fetch_js_data(page, "window.clickSignatures")
        if sigs:
            # Look specifically for delete signatures
            del_sigs = [s for s in sigs if "delete" in s.lower()]
            dropdown_sig = Counter(del_sigs).most_common(1)[0][0] if del_sigs else "Delete"
            
            logger.info("Learned Dropdown Signature: '%s'", dropdown_sig)
            
            # Reset state for test
            await page.reload()
            await asyncio.sleep(4)
            await inject_observers(page)
            
            if await execute_dom_click(page, menu_sig, "Menu"):
                await asyncio.sleep(2) # Extra time for animation
                if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                    ans = await asyncio.to_thread(input, "Did the final modal appear? (Y/N): ")
                    if ans.strip().upper() == 'Y': log_training_result("Step_B", True, dropdown_sig)
                    else: 
                        dropdown_sig = None
                        log_training_result("Step_B", False, "User rejected")
                        await page.reload()
                        await asyncio.sleep(3)
                        await inject_observers(page)

    # --- STEP C: MODAL TRAINING ---
    modal_coords = None
    while not modal_coords:
        print("\n--- STEP C: THE MODAL ---")
        await asyncio.to_thread(input, "Modal is open. Click the final 'Delete' confirmation. Press ENTER.")
        
        coords = await fetch_js_data(page, "window.lastClickRelCoords")
        if coords and coords['relX'] > 0:
            modal_coords = coords
            
            # Reset state for full integration test
            await page.reload()
            await asyncio.sleep(4)
            await inject_observers(page)
            
            await synthetic_mouse_move(page, 0.95, 0.5)
            
            if await execute_dom_click(page, menu_sig, "Menu"):
                await asyncio.sleep(1.5)
                if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                    await asyncio.sleep(2.5) # Wait for modal render
                    await synthetic_mouse_click(page, modal_coords['relX'], modal_coords['relY'])
                    
                    await asyncio.sleep(4)
                    await page.reload()
                    await asyncio.sleep(4)
                    await inject_observers(page)
                    
                    ans = await asyncio.to_thread(input, "Did the comment stay deleted? (Y/N): ")
                    if ans.strip().upper() == 'Y': log_training_result("Step_C", True, "Full Integration")
                    else:
                        modal_coords = None
                        log_training_result("Step_C", False, "Integration Failed")
                        await page.reload()
                        await asyncio.sleep(3)
                        await inject_observers(page)

    print("\n" + "="*60 + "\nPHASE 4: AUTONOMOUS PURGE\n" + "="*60)
    successes, fails = 0, 0

    while successes < 10 and fails < 3:
        logger.info("--- Cycle %s ---", successes + 1)
        await synthetic_mouse_move(page, 0.95, 0.5)
        
        if await execute_dom_click(page, menu_sig, "Menu"):
            await asyncio.sleep(1.5)
            if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                await asyncio.sleep(2.5)
                await synthetic_mouse_click(page, modal_coords['relX'], modal_coords['relY'])
                successes += 1
                fails = 0
                
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await page.reload()
                await asyncio.sleep(4)
                await inject_observers(page)
                continue
                
        fails += 1
        logger.info("Cycle failed. Scrolling...")
        body = await page.select('body')
        if body: await body.click()
        await page.scroll_down(400)
        await asyncio.sleep(2)

    logger.info("Done. Idling...")
    while True: await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())