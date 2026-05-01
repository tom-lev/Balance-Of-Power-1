import json
import time
import re
import os
from playwright.sync_api import sync_playwright


def clean_cia_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('|', ' ')
    abbreviations = {
        r"\bAdm\b": "Admiral", r"\bAdmin\b": "Administrative", r"\bAsst\b": "Assistant",
        r"\bBrig\b": "Brigadier", r"\bCapt\b": "Captain", r"\bCdr\b": "Commander",
        r"\bCdte\b": "Comandante", r"\bChmn\.?(?![a-z])": "Chairman", r"\bCol\b": "Colonel",
        r"\bCtte\b": "Committee", r"\bDel\b": "Delegate", r"\bDep\b": "Deputy",
        r"\bDept\b": "Department", r"\bDir\b": "Director", r"\bDiv\b": "Division",
        r"\bDr\b": "Doctor", r"\bEng\b": "Engineer", r"\bFd\. Mar\b": "Field Marshal",
        r"\bFed\b": "Federal", r"\bGen\b": "General", r"\bGovt\.?": "Government", r"\bGovt\b": "Government",
        r"\bIntl\b": "International", r"\bLt\b": "Lieutenant", r"\bMaj\b": "Major",
        r"\bMar\b": "Marshal", r"\bMbr\b": "Member", r"\bMin\b": "Minister",
        r"\bNDE\b": "No Diplomatic Exchange", r"\bOrg\b": "Organization",
        r"\bPres\.?(?![a-z])": "President", r"\bProf\b": "Professor", r"\bRAdm\b": "Rear Admiral",
        r"\bRet\b": "Retired", r"\bSec\b": "Secretary", r"\bVAdm\b": "Vice Admiral",
        r"\bVMar\b": "Vice Marshal"
    }
    cleaned = text
    for abbrev, full in abbreviations.items():
        cleaned = re.sub(abbrev, full, cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()


def is_top_leader(role):
    role_lower = role.lower().strip()
    role_normalized = role_lower.rstrip(".")

    DISQUALIFIERS = [
        "deputy", "vice", "assistant", "minister of", "minister for",
        "head of office", "head of cabinet", "cabinet",
        "central bank", "national bank", "director", "chief of staff",
        "acting minister", "exchequer", "representative"
    ]
    if any(d in role_lower for d in DISQUALIFIERS):
        return False

    if role_normalized.startswith("president"):
        remainder = role_normalized[len("president"):].strip()
        if not remainder:
            return True
        if remainder.startswith("("):
            return True
        ALLOWED_SUFFIXES = [
            "of the republic", "of the state", "of the bolivarian",
            "of the transitional", "of the federal", "of the islamic",
            ", state affairs commission",
            ", swiss confederation",
        ]
        if any(remainder.startswith(s) for s in ALLOWED_SUFFIXES):
            return True
        return False

    HEAD_ROLES = [
        "prime minister", "king", "queen", "chancellor",
        "emperor", "supreme leader", "supreme pontiff",
        "sovereign", "amir", "sultan",
        "governor general", "grand duke",
        "prince", "captain regent",
        "head of state", "head of government", "chief of state",
        "federal councillor",
        "general secretary",
        "chairman, sovereignty council",
        "president, state affairs commission",
        "governor",
        "premier",
        "acting president",
        "acting prime minister",
    ]
    return any(role_normalized == r or role_normalized.startswith(r) for r in HEAD_ROLES)


def run_scraper():
    all_results = []
    base_url = "https://www.cia.gov"
    index_url = "https://www.cia.gov/resources/world-leaders/foreign-governments/"

    with sync_playwright() as p:
        headless = os.environ.get("CI", "false") == "true"
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = context.new_page()
        # Hide the webdriver flag that headless Chrome exposes to bot detectors
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🔗 Loading index page...")
        page.goto(index_url, wait_until="networkidle")
        # Wait for at least one country link to confirm real content loaded
        try:
            page.wait_for_selector(
                'main a[href*="/world-leaders/foreign-governments/"]',
                timeout=15000,
            )
        except Exception:
            print("⚠️  Timed out waiting for country links — page may be blocked or empty.")

        print("⚡ Selecting 'All' option...")
        try:
            page.select_option("select.per-page", label="All")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        except Exception:
            print("⚠️  Could not switch to 'All', continuing.")

        links = page.locator('main a[href*="/world-leaders/foreign-governments/"]').all()
        all_country_urls = []
        for l in links:
            href = l.get_attribute("href")
            if href and "/foreign-governments/" in href:
                full_path = base_url + href if href.startswith("/") else href
                if full_path.strip("/") != index_url.strip("/") and full_path not in all_country_urls:
                    all_country_urls.append(full_path)

        print(f"📊 Found {len(all_country_urls)} countries.")

        skipped = []
        failed = []

        for i, url in enumerate(all_country_urls):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                country_name = clean_cia_text(page.locator("h1").inner_text())
                leaders = []
                leader_elements = page.locator('.leader-info').all()

                seen = set()
                for el in leader_elements:
                    raw_text = el.inner_text().strip()
                    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                    if len(lines) >= 2:
                        role = clean_cia_text(lines[0])
                        name = clean_cia_text(lines[-1])
                        key = (role.lower(), name.lower())
                        if is_top_leader(role) and key not in seen:
                            seen.add(key)
                            leaders.append({"role": role, "name": name})

                if leaders:
                    all_results.append({"country": country_name, "leaders": leaders})
                    print(f"[{i+1}/{len(all_country_urls)}] ✅ {country_name}: {len(leaders)} leaders")
                else:
                    skipped.append(country_name)
                    first_roles = [clean_cia_text(el.inner_text().split('\n')[0]) for el in leader_elements[:3]]
                    print(f"[{i+1}/{len(all_country_urls)}] — {country_name}: filtered (roles found: {first_roles})")

            except Exception as e:
                failed.append(url)
                print(f"❌ Error at {url}: {e}")

        browser.close()

        print(f"\n📊 Summary:")
        print(f"  ✅ Countries with leaders: {len(all_results)}")
        print(f"  — Filtered (no matching roles): {len(skipped)}")
        for s in skipped:
            print(f"      • {s}")
        print(f"  ❌ Technical errors: {len(failed)}")
        for f_ in failed:
            print(f"      • {f_}")

    json_path = "top_world_leaders.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    print(f"\n💾 JSON saved: {json_path}")
    print("\n✨ Scrape complete!")


if __name__ == "__main__":
    run_scraper()
