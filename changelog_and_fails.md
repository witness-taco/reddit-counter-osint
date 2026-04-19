### Architectural Evolution Log: Project Stealth

**Iteration 1: Escaping the Middleware (`vision_agent.py`)**
* **The Bottleneck:** Tried an AI agent before pivoting to "what we know works". The Hermes Agent CLI framework was too rigid. It relied on brittle system prompts that forced the LLM to hallucinate parameters and attempt to parse the local CDP endpoint as a target URL.
* **The Countermeasure:** We dropped the abstraction layer entirely. We built a direct Python orchestrator that handles the Chrome DevTools Protocol (CDP) via `nodriver` and queries the local Ollama instance (`llama3.2-vision:11b`) via a direct REST call. This gave us absolute control over the execution loop and allowed us to bypass Cloudflare on AccuWeather successfully.

**Iteration 2: Hybrid Determinism (`complex_agent.py`)**
* **The Bottleneck:** Relying entirely on a Vision-Language Model to find and click tiny, repetitive elements (like "Add to basket" buttons) resulted in high latency and hallucinated targets.
* **The Countermeasure:** We transitioned to a Hybrid Deterministic Architecture against the `toscrape` sandbox. We relegated the VLM to high-level semantic routing ("Are we blocked? Did the page load?"), and used native CDP CSS selectors for precise DOM traversal, extraction, and pagination. 

**Iteration 3: React Event Forgery (`todomvc_agent.py`)**
* **The Bottleneck:** When targeting a React environment (TodoMVC), the script could input text, but the UI ignored it. React's synthetic event listeners do not recognize standard script-injected text; they require native hardware-level triggers.
* **The Countermeasure:** We implemented low-level CDP keyboard dispatching. By explicitly sending the native `keyDown` and `keyUp` events for Keycode 13 (Enter), we successfully forged human keystrokes, forcing the React framework's `onSubmit` listeners to fire.

**Iteration 4: Shadow DOM X-Ray (`reddit_learner_agent.py`)**
* **The Bottleneck:** Deployed against Reddit's live "Shreddit" frontend. Standard CDP selectors failed completely because Reddit encapsulates its UI inside Web Components (Shadow DOMs). The elements were invisible to standard queries.
* **The Countermeasure:** Implemented Human-in-the-Loop (HITL) Active Learning. We injected a JavaScript observer into the page utilizing `e.composedPath()`. This acted as an X-ray, tracing the user's physical mouse click all the way down through the shadow boundaries to extract the exact dynamic `aria-label` Reddit was using at that moment. The agent learned the signature from the user demonstration and used it to hunt the rest.

**Iteration 5: Defeating Optimistic UI (`reddit_active_learner.py` V2)**
* **The Bottleneck:** The agent clicked everything perfectly, but Reddit's backend silently rejected the requests (`429 Too Many Requests`). The frontend lied, showing a "Comment Deleted" toast even though the database ignored the action—a classic Optimistic UI update. The backend flagged the session because the 10-second VLM inference delay followed by an instant execution was detected as non-human velocity telemetry.
* **The Countermeasure:** We dropped the VLM entirely for micro-interactions to compress execution time. We injected randomized human pacing (`random.uniform()`) between every click phase. Critically, we introduced "The Truth Serum": forcing a hard `page.reload()` after every cycle. This wiped out the frontend lies and synced the agent with the true server state, forcing it to retry rejected deletions.

**Iteration 6: Coordinate Puppeteering (`V1reddit_active_learner.py`)**
* **The Bottleneck:** Reddit's engineers heavily obfuscated the final confirmation modal, making it invisible even to our recursive Shadow DOM clicker, and intentionally disabled `autofocus` to trap the `Enter` key bypass.
* **The Countermeasure:** We abandoned the DOM entirely to test again. We updated the HITL training phase to record the exact `(X, Y)` screen pixels of your physical mouse click on the modal. In the execution phase, we utilize a CDP "ghost mouse" to teleport to those coordinates and execute a hardware-level click. Because this bypasses the HTML/DOM entirely, it is effectively unblockable by frontend obfuscation.



### Additions for the Evolution Log

**Iteration 7: Viewport Scalability & Atomic Training (`V2_reddit_active_learner.py`)**
* **The Bottleneck:** Hardcoding absolute pixel coordinates created a fragile execution state; resizing the window by even a millimeter caused the ghost mouse to click dead air. Additionally, bundled training sequences collapsed entirely if a single dropdown node wasn't found, and synthetic keyboard events (like hitting `Enter`) corrupted the telemetry by logging `(0, 0)` coordinates. 
* **The Countermeasure:** We shifted to Viewport-Relative Coordinates. The JS X-Ray now calculates the exact percentage of the screen width and height (`relX`, `relY`), allowing the Python orchestrator to dynamically recalculate the absolute pixel targets on the fly regardless of window dimensions. We also filtered out synthetic `0, 0` clicks and broke the HITL training into strict, atomic phases (Menu -> Dropdown -> Modal) with forced DOM reloads upon failure to ensure a pristine state.

**Iteration 8: Spatial Jitter & State Memory (`V2_stable_reddit_active_learner.py`)**
* **The Bottleneck:** Repeatedly clicking the exact same relative pixel is a massive red flag for advanced anti-bot telemetry. Furthermore, having to manually retrain the orchestrator on every boot felt like a regression. Finally, Reddit's CDN cache (Eventual Consistency) kept serving "Ghost Comments," causing the script to loop endlessly on a comment that was already deleted.
* **The Countermeasure:** We introduced "The Memory Card" (`reddit_agent_memory.json`) to persist validated signatures and telemetry across sessions, allowing the agent to bypass the training phase entirely on subsequent runs. To defeat velocity and pattern tracking, we implemented a Drag-and-Drop Bounding Box during the HITL phase. By mapping a secure "strike zone" over the target, the agent uses `random.uniform()` to execute a spatial jitter—clicking a completely random pixel *inside* that box on every cycle. Extended randomized delays were added to outwait the CDN cache.

**Iteration 9: Kernel Interception (`V3.1_hardened_reddit_active_learner.py`)**
* **The Bottleneck:** Because the script required deep, 10-15 second `asyncio.sleep()` delays to outwait Reddit's CDN consistency, making mid-execution adjustments was impossible. Pressing `Ctrl+C` sent a lethal `SIGINT` from the Linux kernel, which violently crashed the asynchronous event loop and severed the CDP connection.
* **The Countermeasure:** We hijacked the native OS signal. Using Python's `signal` module, we intercepted the `SIGINT` command and rerouted it to a custom flag switch. Now, pressing `Ctrl+C` acts as a graceful human override, allowing the orchestrator to finish its current micro-task before suspending the execution loop and spawning a CLI pause menu (Resume / Retrain / Exit) without dropping the browser.

---



Iteration,Script,Core Advancement
Foundation,1launch_stealth.py,"Establishing the raw, headless Chrome DevTools Protocol (CDP) connection via nodriver."
Vision Setup,2vision_agent.py,Integrating a local llama3.2-vision:11b instance to visually parse and dismiss GDPR consent modals.
Hybrid Routing,3sandbox_agent.py,Combining semantic VLM state-checking with deterministic DOM selectors to navigate toscrape.com.
React Forgery,4complex_agent.py,Forging native keyDown/keyUp (Keycode 13) CDP events to defeat React's synthetic event listeners on TodoMVC.
Live Target,5reddit_agent.py,"The first Reddit strike, using VLM and aria-label hunting (which highlighted the Shadow DOM bottleneck)."
The Breakthrough,6reddit_learner_agent.py,Human-in-the-Loop active learning using an e.composedPath() X-ray to extract dynamic signatures directly through Shadow boundaries.
Viewport Scalability,V4reddit_active_learner.py,Transitioning to viewport-relative coordinates and atomic training phases to survive window resizing and telemetry corruption.
Spatial Jitter & Memory,V6reddit_active_learner.py,Implementing drag-and-drop bounding boxes for randomized pixel targeting and a persistent memory card to bypass retraining.
Kernel Interception,V7_stealth_orchestrator.py,"Hijacking OS SIGINT commands to create a graceful pause menu, preventing event loop crashes during long CDN waits.