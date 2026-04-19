=working as of 19 Apr 2026=

 _349 comments deleted in one session. no penalties_

**USE V4_hardened_reddit_active_learner.py**



# Reddit Comment Deletion Script

A heavily rate-limited, Human-in-the-Loop (HITL) orchestrator designed to delete your reddit comments

Built for simplicity without relying on bulk API calls that trigger immediate shadowbans. 

It's not fast by design - but reliable. It could easily run headless/cronjob but I chose to have more control and QA for now. 

Uses synthetic Chrome DevTools Protocol (CDP) interactions, spatial jitter, and randomized human pacing, to operate entirely beneath standard anti-bot telemetry thresholds

---

<img width="933" height="869" alt="image" src="https://github.com/user-attachments/assets/7cc10f5a-11f8-4d8a-ae13-750b590d0e4e" />


It will save successful trainings andd be able to pull it up the next time you run the script. 

Asks if you want to run the automation on re-train


---

## The Methodology & Challenges Faced

Building a resilient DOM interaction agent against Reddit's modern frontend ("Shreddit") required navigating several layers of aggressive anti-automation architecture. This project evolved through multiple architectures to reach its current stable state:

* **Evading the Shadow DOM:** Reddit encapsulates its UI elements inside Web Components (Shadow DOMs), making standard CDP selectors blind. We implemented a JavaScript observer utilizing `e.composedPath()` to "X-ray" physical mouse clicks, extracting exact dynamic `aria-label` signatures through the shadow boundaries.
* **Defeating Optimistic UI (The Fake Frontend):** This was the most significant hurdle. Reddit's frontend will frequently show a "Comment Deleted" confirmation toast even if the backend silently rejects the request with a `429 Too Many Requests` error due to non-human interaction velocity. To bypass this, we introduced randomized pacing and forced hard `page.reload()` cycles ("The Truth Serum") after every action to verify the true database state.
* **Modal Obfuscation & Coordinate Puppeteering:** Final confirmation modals lack reliable selectors and disable `autofocus` to trap keyboard bypasses. We shifted to a Viewport-Relative coordinate system, allowing the agent to target elements regardless of window resizing.
* **Spatial Jitter & State Memory:** Repeatedly clicking the exact same pixel guarantees a ban. The active learning phase now requires the user to drag a bounding box over the target area. The agent calculates a randomized "strike zone," clicking a different pixel within that box every cycle. Telemetry is preserved in `reddit_agent_memory.json` to bypass retraining on future runs.
* **Kernel Interception:** Because the script requires deep 10-15 second delays to outwait Reddit's CDN cache, making mid-execution adjustments was difficult. We hijacked the native OS `SIGINT` command. Pressing `Ctrl+C` now acts as a graceful human override, pausing the loop without dropping the browser.


---

## Installation & Quick Start

This tool utilizes local virtual environments to prevent dependency conflicts. You do not need to manually run `pip install` commands.

**Prerequisites:** * Python 3 installed and added to your system PATH.
* Google Chrome installed.

### Windows
1. Download or clone the repository.
2. Double-click `start.bat`.
3. The script will automatically create a virtual environment, install the `nodriver` dependency, and launch the orchestrator.

### Linux / macOS
1. Open your terminal and navigate to the project directory.
2. Make the launcher executable: `chmod +x start.sh`
3. Execute the launcher: `./start.sh`
4. The script will handle the `venv` creation and dependency mapping automatically.

---

## Operation Guide

Once the script launches, a persistent Chrome browser will open.

### Phase 1: Authentication & Setup
1. Log into your Reddit account.
2. Navigate to your Profile and select the **Comments** tab.
3. Return to the terminal and press **ENTER** to begin the training sequence.

### Phase 2: Active Learning (HITL)
If no memory card is detected, the agent requires you to train it on the current iteration of Reddit's UI.
1. **The Menu:** Click the 3-dot overflow menu on a comment.
2. **The Dropdown:** Click "Delete" in the resulting dropdown.
3. **The Bounding Box:** When the final confirmation modal appears, **click and drag** a box across the "Delete" button to establish the synthetic strike zone, then click it normally to finalize the deletion.

### Phase 3: Autonomous Purge
Once telemetry is acquired, you will be prompted to select a deletion limit. The agent will take over, executing the sequence with heavy spatial jitter and randomized CDN wait times. 

**To pause execution at any time:** Press `Ctrl+C` in your terminal
