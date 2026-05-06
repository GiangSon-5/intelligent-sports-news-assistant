import asyncio
from playwright.async_api import async_playwright

# Data Sources and Selectors (Phase 1 & 2)
SOURCES = [
    {
        "name": "THANH NIEN NEWS",
        "url": "https://thanhnien.vn/the-thao.htm",
        "parent_sel": ".box-category-item",
        "link_sel": "h3.box-title-text a, h2.box-title-text a",
        "detail": {
            "title": "h1.detail-title",
            "date": ".detail-time, [data-role='publishdate']",
            "content": ".detail-content p, #main-detail-body p"
        }
    },
    {
        "name": "VNEXPRESS",
        "url": "https://vnexpress.net/the-thao",
        "parent_sel": "article.item-news",
        "link_sel": "h2.title-news a, h3.title-news a",
        "detail": {
            "title": "h1.title-detail",
            "date": "span.date",
            "content": "article.fck_detail p"
        }
    },
    {
        "name": "TUOI TRE NEWS",
        "url": "https://tuoitre.vn/the-thao.htm",
        "parent_sel": ".news-item",
        "link_sel": "a.box-category-link-title",
        "detail": {
            "title": "h1.detail-title",
            "date": ".detail-time",
            "content": ".detail-content p"
        }
    }
]

async def run_professional_demo(page, source):
    """End-to-End Extraction Workflow: Listing -> Navigation -> Attribute Parsing."""
    try:
        # --- PHASE 1: LISTING IDENTIFICATION ---
        print(f"[PROCESS] Accessing Listing Page: {source['name']}")
        await page.goto(source['url'], wait_until="domcontentloaded", timeout=60000)
        
        # Highlight potential target items in the DOM
        await page.evaluate(f'''(sel) => {{
            const items = document.querySelectorAll(sel.parent);
            items.forEach(i => {{
                i.style.border = '2px solid #64748b';
                i.style.position = 'relative';
                const tag = document.createElement('div');
                tag.innerText = 'IDENTIFIED TARGET';
                tag.style.cssText = 'position:absolute; top:0; left:0; background:#64748b; color:white; font-size:10px; padding:2px 6px; z-index:10; font-family:sans-serif; text-transform:uppercase;';
                i.appendChild(tag);
            }});
        }}''', {"parent": source['parent_sel']})
        
        await asyncio.sleep(2)
        
        # --- PHASE 2: TARGET SELECTION & NAVIGATION ---
        print(f"[ACTION] Automated selection of primary article for deep-parsing...")
        target_link = page.locator(source['link_sel']).first
        await target_link.scroll_into_view_if_needed()
        
        # Highlight selection before execution
        await target_link.evaluate("el => el.style.outline = '4px solid #ef4444'")
        await asyncio.sleep(1)
        await target_link.click()
        
        # --- PHASE 3: ATTRIBUTE EXTRACTION ---
        print(f"[PROCESS] Entered Detail Page. Executing Attribute Extraction...")
        await page.wait_for_load_state("domcontentloaded")
        
        await page.evaluate(f'''(det) => {{
            // 1. Title Extraction
            const t = document.querySelector(det.title);
            if (t) {{
                t.style.border = '3px solid #ef4444';
                t.insertAdjacentHTML('afterbegin', '<span style="background:#ef4444;color:white;font-size:11px;padding:2px 8px;margin-right:10px;font-family:sans-serif;">TARGET: TITLE</span>');
            }}
            // 2. Metadata Extraction (Date)
            const d = document.querySelector(det.date);
            if (d) {{
                d.style.border = '2px solid #10b981';
                d.insertAdjacentHTML('afterbegin', '<span style="background:#10b981;color:white;font-size:11px;padding:2px 8px;margin-right:10px;font-family:sans-serif;">TARGET: PUBLISH DATE</span>');
            }}
            // 3. Content Body Extraction
            const p = document.querySelectorAll(det.content);
            p.forEach(item => {{
                item.style.backgroundColor = 'rgba(14, 165, 233, 0.1)';
                item.style.borderLeft = '4px solid #0ea5e9';
            }});
        }}''', source['detail'])

        print(f"[SUCCESS] {source['name']} data mapping completed successfully.")
        
        # Automated scroll-through for validation
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.8)

    except Exception as e:
        print(f"[ERROR] Workflow for {source['name']} failed: {e}")

async def main():
    async with async_playwright() as p:
        print("\n" + "="*70)
        print("MULTI-TAB AUTOMATED CRAWLING DEMO (TECHNICAL STAKEHOLDERS)")
        print("Workflow: Simultaneous Identification -> Parallel Parsing -> Inspection Mode")
        print("="*70 + "\n")
        
        # Launch browser and keep the window open
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        
        # Initialize parallel processing tasks for 3 tabs
        tasks = []
        for source in SOURCES:
            page = await context.new_page()
            # Add demo task to the execution list
            tasks.append(run_professional_demo(page, source))
            # Small delay between tab openings to prevent performance spikes
            await asyncio.sleep(1)

        # Execute all 3 tabs concurrently
        await asyncio.gather(*tasks)

        print("\n" + "*"*25 + " ALL TASKS COMPLETED " + "*"*25)
        print("Inspection Mode: Tabs are kept OPEN for your review.")
        print("Press ENTER in this terminal when you want to close the browser.")
        
        # Keep browser open until user presses Enter
        await asyncio.get_event_loop().run_in_executor(None, input)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
