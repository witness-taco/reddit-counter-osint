import asyncio
import json
import logging
import os
import random
import time
import shutil
import nodriver as uc
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("nodriver.core.connection").setLevel(logging.CRITICAL)

PROFILE_DIR = os.path.expanduser('~/.config/nodriver_reddit_profile')
TARGET_URL = "https://www.reddit.com/"
LOG_FILE = "agent_training_metrics.json"
MEMORY_FILE = "reddit_agent_memory.json"

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

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f: return json.load(f)
        except: pass
    return None

def backup_memory():
    """Renames the current memory file to preserve it before retraining."""
    if os.path.exists(MEMORY_FILE):
        backup_name = f"reddit_agent_memory_backup_{int(time.time())}.json"
        os.rename(MEMORY_FILE, backup_name)
        logger.info("Previous memory preserved as '%s'", backup_name)

def save_memory(menu_sig, dropdown_sig, bounding_box):
    with open(MEMORY_FILE, 'w') as f:
        json.dump({
            "menu_signature": menu_sig,
            "dropdown_signature": dropdown_sig,
            "modal_bounding_box": bounding_box
        }, f, indent=4)
    logger.info("Progress saved to Memory Card.")

async def inject_observers(page):
    """Injects JS observers capturing clicks AND drag-and-drop bounding boxes."""
    await page.evaluate("""
        window.clickSignatures = [];
        window.lastBoundingBox = null;
        let startX = 0, startY = 0;
        
        document.addEventListener('mousedown', function(e) {
            startX = e.clientX; startY = e.clientY;
        }, {capture: true});

        document.addEventListener('mouseup', function(e) {
            let dx = Math.abs(e.clientX - startX);
            let dy = Math.abs(e.clientY - startY);
            if (dx > 5 || dy > 5) {
                window.lastBoundingBox = {
                    relMinX: Math.min(startX, e.clientX) / window.innerWidth,
                    relMaxX: Math.max(startX, e.clientX) / window.innerWidth,
                    relMinY: Math.min(startY, e.clientY) / window.innerHeight,
                    relMaxY: Math.max(startY, e.clientY) / window.innerHeight
                };
            }
        }, {capture: true});
        
        document.addEventListener('click', function(e) {
            if (e.clientX === 0 && e.clientY === 0) return;
            const path = e.composedPath();
            for (let node of path) {
                if (node && node.nodeType === Node.ELEMENT_NODE) {
                    let tag = node.tagName.toLowerCase();
                    let role = node.getAttribute('role');
                    if (tag === 'button' || role === 'button' || role === 'menuitem') {
                        let sig = node.getAttribute('aria-label') || node.innerText;
                        if (sig && sig.trim() !== "") { 
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

async def synthetic_mouse_move(page, rel_x, rel_y, is_custom=False):
    viewport = await fetch_js_data(page, "{w: window.innerWidth, h: window.innerHeight}")
    x, y = int(rel_x * viewport['w']), int(rel_y * viewport['h'])
    
    if is_custom:
        await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseMoved", x=x+random.randint(-100,100), y=y+random.randint(-100,100)))
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseMoved", x=x, y=y))
    await asyncio.sleep(0.2)

async def synthetic_mouse_click(page, bounding_box, is_custom=False):
    """Executes click anywhere inside the established bounding box to create spatial jitter."""
    viewport = await fetch_js_data(page, "{w: window.innerWidth, h: window.innerHeight}")
    
    x = int(random.uniform(bounding_box['relMinX'], bounding_box['relMaxX']) * viewport['w'])
    y = int(random.uniform(bounding_box['relMinY'], bounding_box['relMaxY']) * viewport['h'])
    
    logger.info("Agent: Mapped ghost mouse to X:%s, Y:%s (Inside Box)...", x, y)
    
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
    
    hover_time = random.uniform(0.5, 1.5) if is_custom else random.uniform(0.3, 0.6)
    await asyncio.sleep(hover_time)
    
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mousePressed", x=x, y=y, button=left_btn, click_count=1))
    await asyncio.sleep(random.uniform(0.08, 0.15))
    await page.send(uc.cdp.input_.dispatch_mouse_event(type_="mouseReleased", x=x, y=y, button=left_btn, click_count=1))

async def execute_dom_click(page, signature, step_name):
    """Dynamically applies ghost mouse jitter to DOM elements."""
    logger.info("Agent: Searching for %s ('%s')...", step_name, signature)
    target = await page.find(signature, timeout=4)
    
    if target:
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await target.click()
        return True
    return False

async def main():
    os.makedirs(PROFILE_DIR, exist_ok=True)
    browser = await uc.start(headless=False, browser_executable_path='/usr/bin/google-chrome', user_data_dir=PROFILE_DIR)
    page = await browser.get(TARGET_URL)
    
    app_running = True
    
    while app_running:
        print("\n" + "="*60)
        print(" Reddit Comment Deletion ANTI-OSINT ")
        print("="*60)
        
        mode_input = await asyncio.to_thread(input, "Select Mode:\n[1] Regular (Fast, safe limits)\n[2] Custom (Heavy jitter, infinite loops)\n[3] Exit\nSelection: ")
        if mode_input.strip() == "3":
            break
            
        is_custom = mode_input.strip() == "2"
        
        if is_custom:
            limit_input = await asyncio.to_thread(input, "How many deletions? (Type number or 'non-stop'): ")
            max_deletions = float('inf') if limit_input.strip().lower() == 'non-stop' else int(limit_input)
        else:
            limit_input = await asyncio.to_thread(input, "How many deletions? (1-20, default 10): ")
            try: max_deletions = int(limit_input) if 0 < int(limit_input) <= 20 else 10
            except: max_deletions = 10

        menu_sig, dropdown_sig, modal_box = None, None, None
        memory = load_memory()

        if memory:
            print("\n" + "="*60 + "\nMEMORY CARD DETECTED\n" + "="*60)
            mem_choice = await asyncio.to_thread(input, "[1] Use Saved Data (Skip Training)\n[2] Retrain (Creates backup of old data)\nSelection: ")
            
            if mem_choice.strip() == "1":
                menu_sig = memory.get("menu_signature")
                dropdown_sig = memory.get("dropdown_signature")
                modal_box = memory.get("modal_bounding_box")
                logger.info("Bypassing training phases using saved telemetry.")
            else:
                backup_memory()
                
        # --- TRAINING SEQUENCE ---
        if not modal_box:
            await asyncio.to_thread(input, "\nNavigate to Comments. Press ENTER when ready to begin training.")
            await inject_observers(page)

            while not menu_sig:
                print("\n--- STEP A: THE MENU ---")
                await asyncio.to_thread(input, "Click the 3-dot menu. Press ENTER.")
                sigs = await fetch_js_data(page, "window.clickSignatures")
                if sigs:
                    menu_sig = Counter([s for s in sigs if "delete" not in s.lower()]).most_common(1)[0][0] if any("delete" not in s.lower() for s in sigs) else Counter(sigs).most_common(1)[0][0]
                    body = await page.select('body')
                    if body: await body.click()
                    await asyncio.sleep(1)
                    
                    if await execute_dom_click(page, menu_sig, "Menu"):
                        ans = await asyncio.to_thread(input, "Did the menu open? (Y/N): ")
                        if ans.strip().upper() != 'Y': menu_sig = None

            while not dropdown_sig:
                print("\n--- STEP B: THE DROPDOWN ---")
                await asyncio.to_thread(input, "Menu is open. Click 'Delete' in the dropdown. Press ENTER.")
                sigs = await fetch_js_data(page, "window.clickSignatures")
                if sigs:
                    del_sigs = [s for s in sigs if "delete" in s.lower()]
                    dropdown_sig = Counter(del_sigs).most_common(1)[0][0] if del_sigs else "Delete"
                    
                    await page.reload()
                    await asyncio.sleep(4)
                    await inject_observers(page)
                    
                    if await execute_dom_click(page, menu_sig, "Menu"):
                        await asyncio.sleep(2)
                        if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                            ans = await asyncio.to_thread(input, "Did the modal appear? (Y/N): ")
                            if ans.strip().upper() != 'Y': dropdown_sig = None

            while not modal_box:
                print("\n--- STEP C: THE MODAL BOUNDING BOX ---")
                print("1. Click and DRAG a box across the 'Delete' button.")
                print("2. Release the mouse.")
                print("3. Click it normally to delete the comment.")
                await asyncio.to_thread(input, "Press ENTER *after* the comment is gone.")
                
                box = await fetch_js_data(page, "window.lastBoundingBox")
                if box and box['relMaxX'] > box['relMinX']:
                    modal_box = box
                    logger.info("Bounding Box Acquired.")
                    
                    await page.reload()
                    await asyncio.sleep(4)
                    await inject_observers(page)
                    
                    await synthetic_mouse_move(page, 0.95, 0.5, is_custom)
                    if await execute_dom_click(page, menu_sig, "Menu"):
                        await asyncio.sleep(1.5)
                        if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                            await asyncio.sleep(2.5)
                            await synthetic_mouse_click(page, modal_box, is_custom)
                            
                            await asyncio.sleep(4)
                            await page.reload()
                            await asyncio.sleep(4)
                            await inject_observers(page)
                            
                            ans = await asyncio.to_thread(input, "Did the comment stay deleted? (Y/N): ")
                            if ans.strip().upper() == 'Y':
                                save_memory(menu_sig, dropdown_sig, modal_box)
                            else:
                                modal_box = None

        # --- THE STAGING AREA ---
        print("\n" + "="*60 + "\nPHASE 4: AUTONOMOUS PURGE\n" + "="*60)
        print(">>> TARGET ACQUIRED AND LOCKED <<<")
        print("TIP: You can press Ctrl+C at any time to pause the execution.\n")
        await asyncio.to_thread(input, "Navigate to the exact page you want to purge. Press ENTER to commence: ")
        
        successes, fails = 0, 0
        cycle_aborted = False

        while successes < max_deletions and fails < 3:
            try:
                logger.info("--- Cycle %s ---", successes + 1)
                await synthetic_mouse_move(page, 0.95, 0.5, is_custom)
                
                if await execute_dom_click(page, menu_sig, "Menu"):
                    await asyncio.sleep(1.5)
                    if await execute_dom_click(page, dropdown_sig, "Dropdown"):
                        await asyncio.sleep(2.5)
                        await synthetic_mouse_click(page, modal_box, is_custom)
                        successes += 1
                        fails = 0
                        
                        delay = random.uniform(6.0, 14.0) if is_custom else random.uniform(3.0, 5.0)
                        logger.info("Waiting %.2fs for CDN consistency...", delay)
                        await asyncio.sleep(delay)
                        
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
                
            except KeyboardInterrupt:
                print("\n\n" + "!"*60)
                print(" EXECUTION HALTED BY HUMAN OVERRIDE ")
                print("!"*60)
                pause_choice = await asyncio.to_thread(input, "[1] Resume Execution\n[2] Start Over (Main Menu)\n[3] Exit Script\nSelection: ")
                if pause_choice.strip() == "1":
                    print("Resuming operation...")
                    continue
                elif pause_choice.strip() == "2":
                    cycle_aborted = True
                    break
                else:
                    app_running = False
                    break
                    
        if not app_running:
            break
            
        if not cycle_aborted:
            if fails >= 3:
                logger.warning("Execution terminated: Failed 3 consecutive cycles.")
            else:
                logger.info("Target deletions met: %s", successes)
                
            post_choice = await asyncio.to_thread(input, "\nSequence Complete. \n[1] Return to Main Menu\n[2] Exit Script\nSelection: ")
            if post_choice.strip() != "1":
                break

    logger.info("Gracefully shutting down orchestrator...")

if __name__ == '__main__':
    # Wrapping the runner in a basic try-except to catch stray Ctrl+C during deep waits
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess terminated.")